import contextlib
import errno
import io
import json
import socket
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import workflow as w
from local_api_errors import LocalAPIError, describe_failure

URL='http://localhost:23119/api/users/0/items/top?limit=1'

class NetworkDiagnostics(unittest.TestCase):
    def test_wrapped_and_direct_permission_denied(self):
        for n in [errno.EPERM,errno.EACCES]:
            for error in [OSError(n,'denied'),URLError(OSError(n,'denied'))]:
                with self.subTest(n=n,wrapped=isinstance(error,URLError)):
                    r=describe_failure(URL,error)
                    self.assertEqual(r['error_code'],'LOCAL_API_PERMISSION_DENIED')
                    self.assertTrue(r['retry_with_permission'])

    def test_http_403_is_not_a_sandbox_denial(self):
        r=describe_failure(URL,HTTPError(URL,403,'Forbidden',{},None))
        self.assertEqual(r['error_code'],'ZOTERO_API_FORBIDDEN')
        self.assertFalse(r['retry_with_permission'])
        self.assertEqual(r['http_status'],403)

    def test_http_404_reports_request_problem(self):
        r=describe_failure(URL,HTTPError(URL,404,'Not Found',{},None))
        self.assertEqual(r['error_code'],'ZOTERO_API_NOT_FOUND')
        self.assertFalse(r['retry_with_permission'])

    def test_connection_refused_is_distinct(self):
        r=describe_failure(URL,URLError(ConnectionRefusedError(errno.ECONNREFUSED,'refused')))
        self.assertEqual(r['error_code'],'ZOTERO_API_CONNECTION_REFUSED')
        self.assertFalse(r['retry_with_permission'])

    def test_timeout_and_unknown_failure_are_not_permission_evidence(self):
        for error in [URLError(socket.timeout('timeout')),TimeoutError('timeout')]:
            self.assertEqual(describe_failure(URL,error)['error_code'],'ZOTERO_API_TIMEOUT')
        r=describe_failure(URL,URLError('unknown'))
        self.assertEqual(r['error_code'],'ZOTERO_API_UNREACHABLE')
        self.assertFalse(r['retry_with_permission'])

    def test_api_does_not_retry_or_escalate_itself(self):
        with patch.object(w.urllib.request,'build_opener') as factory:
            factory.return_value.open.side_effect=URLError(PermissionError(errno.EPERM,'denied'))
            with self.assertRaises(LocalAPIError):w.api('/items/top?limit=1')
            factory.return_value.open.assert_called_once()

    def test_cli_emits_structured_diagnostic(self):
        with patch.object(sys,'argv',['workflow.py','doctor']),patch.object(w,'api',side_effect=LocalAPIError(URL,URLError(PermissionError(errno.EPERM,'denied')))),contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(w.main(),1)
        result=json.loads(output.getvalue())
        self.assertEqual(result['error_code'],'LOCAL_API_PERMISSION_DENIED')
        self.assertTrue(result['retry_with_permission'])

    def test_doctor_is_read_only_and_checks_actual_endpoint(self):
        with patch.object(w,'api',return_value=[]) as request,patch.object(w,'atomic') as write:
            result=w.doctor()
            request.assert_called_once_with('/items/top?limit=1')
            write.assert_not_called()
            self.assertEqual(result['state'],'READY')
            self.assertFalse(result['vault_modified'])

if __name__=='__main__':unittest.main()
