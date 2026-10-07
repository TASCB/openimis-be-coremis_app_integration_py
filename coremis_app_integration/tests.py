import base64
import json
import tempfile
from pathlib import Path

from django.test import SimpleTestCase, override_settings

from coremis_app_integration.esb_client.envelope import (
    _compact_json, raw_json_member, signed_content_candidates,
)
from coremis_app_integration.govesb_inbound import signed_reply, verify_inbound


class RawJsonMemberTest(SimpleTestCase):
    def test_returns_exact_source_text(self):
        raw = '{ "data" : {"a": 1.0, "u": "\\/x\\u00e9"} , "signature":"S"}'
        self.assertEqual(raw_json_member(raw, 'data'), '{"a": 1.0, "u": "\\/x\\u00e9"}')
        self.assertEqual(raw_json_member(raw, 'signature'), '"S"')
        self.assertEqual(raw_json_member(raw.encode(), 'data'), '{"a": 1.0, "u": "\\/x\\u00e9"}')

    def test_order_and_nesting_do_not_matter(self):
        raw = '{"signature":"S","x":{"data":"inner"},"data":[1,{"data":2}]}'
        self.assertEqual(raw_json_member(raw, 'data'), '[1,{"data":2}]')

    def test_missing_or_broken(self):
        self.assertIsNone(raw_json_member('{"signature":"S"}', 'data'))
        self.assertIsNone(raw_json_member('[1,2]', 'data'))
        self.assertIsNone(raw_json_member('{"data":', 'data'))
        self.assertIsNone(raw_json_member(None, 'data'))

    def test_candidates_put_raw_first_and_skip_duplicates(self):
        data = {'a': 1}
        self.assertEqual(signed_content_candidates('{"data": {"a": 1}}', data), ['{"a": 1}', '{"a":1}'])
        self.assertEqual(signed_content_candidates('{"data":{"a":1}}', data), ['{"a":1}'])
        self.assertEqual(signed_content_candidates(None, data), ['{"a":1}'])


def _keys():
    from ellipticcurve import PrivateKey
    ours, esb = PrivateKey(), PrivateKey()
    folder = Path(tempfile.mkdtemp())
    (folder / 'client.pem').write_text(ours.toPem())
    esb_pub = base64.b64encode(esb.publicKey().toDer()).decode()
    return ours, esb, folder / 'client.pem', esb_pub


class SignatureOverRawTextTest(SimpleTestCase):
    def setUp(self):
        self.ours, self.esb, self.key_path, self.esb_pub = _keys()

    def _esb(self):
        return {'ENABLED': True, 'CLIENT_PRIVATE_KEY': str(self.key_path),
                'GOV_ESB_PUBLIC_KEY_B64': self.esb_pub}

    def test_inbound_signed_over_non_compact_text_verifies_with_raw(self):
        from ellipticcurve import Ecdsa
        data_text = '{"esbBody": {"amount": 1.0, "path": "a\\/b"}}'
        raw = '{"data": ' + data_text + ', "signature": "' + Ecdsa.sign(data_text, self.esb).toBase64() + '"}'
        body = json.loads(raw)
        with override_settings(ESB=self._esb()):
            payload, verified, error = verify_inbound(body, raw)
            self.assertEqual((payload, verified, error), ({'amount': 1.0, 'path': 'a/b'}, True, None))
            # Re-serialising alone loses the original bytes, so it cannot verify this message.
            self.assertEqual(verify_inbound(body)[2], 'Invalid GovESB signature')

    def test_compact_fallback_still_verifies(self):
        from ellipticcurve import Ecdsa
        data = {'esbBody': {'a': 1}}
        body = {'data': data, 'signature': Ecdsa.sign(_compact_json(data), self.esb).toBase64()}
        with override_settings(ESB=self._esb()):
            self.assertEqual(verify_inbound(body)[:2], ({'a': 1}, True))

    def test_signed_reply_shape_and_signature(self):
        from ellipticcurve import Ecdsa
        from ellipticcurve import Signature as EcSignature
        with override_settings(ESB=self._esb()):
            text = signed_reply(True, esb_body={'message': {'x': 'é'}})
        reply = json.loads(text)
        self.assertEqual(reply['data'], {'success': True, 'esbBody': {'message': {'x': 'é'}}})
        self.assertTrue(Ecdsa.verify(raw_json_member(text, 'data'),
                                     EcSignature.fromBase64(reply['signature']), self.ours.publicKey()))

    def test_failure_reply_carries_message(self):
        with override_settings(ESB=self._esb()):
            reply = json.loads(signed_reply(False, message='Invalid GovESB signature'))
        self.assertEqual(reply['data'], {'success': False, 'message': 'Invalid GovESB signature'})
        self.assertIn('signature', reply)

    def test_unsigned_without_esb_or_usable_key(self):
        with override_settings(ESB=None):
            self.assertEqual(json.loads(signed_reply(True, esb_body={})), {'data': {'success': True, 'esbBody': {}}})
        with override_settings(ESB={**self._esb(), 'CLIENT_PRIVATE_KEY': '/nonexistent.pem'}):
            self.assertNotIn('signature', json.loads(signed_reply(False, message='x')))
