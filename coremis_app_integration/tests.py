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


class XmlEnvelopeTest(SimpleTestCase):
    def setUp(self):
        self.ours, self.esb, self.key_path, self.esb_pub = _keys()

    def _esb(self):
        return {'ENABLED': True, 'CLIENT_PRIVATE_KEY': str(self.key_path),
                'GOV_ESB_PUBLIC_KEY_B64': self.esb_pub}

    def test_request_is_signed_over_the_compact_data_element(self):
        from ellipticcurve import Ecdsa
        from ellipticcurve import Signature as EcSignature
        from coremis_app_integration.esb_client.envelope import EnvelopeBuilder, raw_xml_element
        from coremis_app_integration.esb_client.enums import ESBRequestType
        from coremis_app_integration.esb_client.signatures import SignatureService

        builder = EnvelopeBuilder(SignatureService(self.key_path, self.esb_pub))
        text = builder.build_xml(api_code='CODE1', payload={'requestdata': '<Gepg>\n  <A>1</A>\n  <B/>\n</Gepg>'},
                                 request_type=ESBRequestType.NORMAL)
        data = raw_xml_element(text, 'data')
        self.assertEqual(data, '<data><apiCode>CODE1</apiCode><esbBody><Gepg><A>1</A><B></B></Gepg></esbBody></data>')
        self.assertTrue(text.startswith('<esbrequest><data>') and text.endswith('</signature></esbrequest>'))
        signature = text.split('<signature>')[1].split('</signature>')[0]
        self.assertTrue(Ecdsa.verify(data, EcSignature.fromBase64(signature), self.ours.publicKey()))

    def _signed_by_esb(self, data):
        from ellipticcurve import Ecdsa
        return f'<esbrequest>{data}<signature>{Ecdsa.sign(data, self.esb).toBase64()}</signature></esbrequest>'

    def test_inbound_xml_verifies_over_the_received_text(self):
        from coremis_app_integration.govesb_inbound import verify_inbound_xml
        data = '<data>\n <esbBody><Gepg><X a="1">é &amp; b</X></Gepg></esbBody>\n</data>'
        with override_settings(ESB=self._esb()):
            body, verified, error = verify_inbound_xml(self._signed_by_esb(data))
            self.assertEqual((body, verified, error), ('<Gepg><X a="1">é &amp; b</X></Gepg>', True, None))
            tampered = self._signed_by_esb(data).replace('é', 'e')
            self.assertEqual(verify_inbound_xml(tampered)[2], 'Invalid GovESB signature')
            self.assertEqual(verify_inbound_xml('<esbrequest><data></data></esbrequest>')[2],
                             'Missing GovESB signed envelope (data/signature)')
            self.assertTrue(verify_inbound_xml('not xml')[2].startswith('Invalid XML'))

    def test_xml_reply_shape_and_signature(self):
        from ellipticcurve import Ecdsa
        from ellipticcurve import Signature as EcSignature
        from coremis_app_integration.esb_client.envelope import raw_xml_element
        from coremis_app_integration.govesb_inbound import signed_reply_xml
        with override_settings(ESB=self._esb()):
            text = signed_reply_xml(True, esb_body='<Ack><Code>7101</Code></Ack>')
            failure = signed_reply_xml(False, message='Unknown <id>')
        data = raw_xml_element(text, 'data')
        self.assertEqual(data, '<data><success>true</success><esbBody><Ack><Code>7101</Code></Ack></esbBody></data>')
        signature = text.split('<signature>')[1].split('</signature>')[0]
        self.assertTrue(Ecdsa.verify(data, EcSignature.fromBase64(signature), self.ours.publicKey()))
        self.assertIn('<message>Unknown &lt;id&gt;</message>', failure)

    def test_client_reads_a_signed_xml_reply(self):
        from types import SimpleNamespace
        from unittest import mock
        from coremis_app_integration.esb_client.client import ESBClient
        from coremis_app_integration.esb_client.signatures import SignatureService

        data = '<data><success>true</success><requestId>R9</requestId><esbBody><Ack>7101</Ack></esbBody></data>'
        client = ESBClient.__new__(ESBClient)
        client._settings = SimpleNamespace(verify_response_signature=True)
        client._signer = SignatureService(self.key_path, self.esb_pub)
        reply = client._parse_xml_response(mock.Mock(text=self._signed_by_esb(data).replace('esbrequest', 'esbresponse')))
        self.assertEqual((reply.ok, reply.signature_verified, reply.request_id, reply.esb_body, reply.success),
                         (True, True, 'R9', '<Ack>7101</Ack>', True))
        bad = client._parse_xml_response(mock.Mock(text=self._signed_by_esb(data).replace('R9', 'R8')))
        self.assertEqual((bad.ok, bad.error), (False, 'Invalid ESB response signature'))


class CountrywideHookLoginTest(SimpleTestCase):
    def _run(self, username):
        from unittest import mock
        from coremis_app_integration.rbac import countrywide
        user = mock.Mock(login_name=username)
        with mock.patch('core.models.InteractiveUser.objects') as objects, \
                mock.patch.object(countrywide, 'has_countrywide_role', return_value=True), \
                mock.patch.object(countrywide, 'grant_districts') as grant:
            objects.filter.return_value.first.return_value = user
            countrywide.on_user_after_mutation(
                None, mutation_class='UpdateUserMutation', data={'username': username},
                user=mock.Mock(id_for_audit=1), error_messages=[])
        return objects.filter.call_args.kwargs['login_name'], grant

    def test_long_login_is_looked_up_in_full(self):
        looked_up, grant = self._run('commanager2')
        self.assertEqual(looked_up, 'commanager2')
        grant.assert_called_once()

    def test_short_login_still_works(self):
        looked_up, grant = self._run('comtest1')
        self.assertEqual(looked_up, 'comtest1')
        grant.assert_called_once()
