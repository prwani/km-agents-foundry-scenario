import os
import unittest
from unittest.mock import patch

from km_agents.config import ConfigurationError
from km_agents.identity import foundry_obo_credential


class IdentityTests(unittest.TestCase):
    def test_foundry_obo_requires_user_assertion_and_confidential_client_settings(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ConfigurationError, "Foundry OBO"):
                foundry_obo_credential("")

    def test_foundry_obo_builds_confidential_credential(self):
        with patch.dict(
            os.environ,
            {
                "ENTRA_TENANT_ID": "tenant",
                "ENTRA_PORTAL_CLIENT_ID": "client",
                "ENTRA_CLIENT_SECRET": "secret",
            },
            clear=True,
        ), patch("km_agents.identity.OnBehalfOfCredential") as credential:
            result = foundry_obo_credential("user-token")

        self.assertIs(result, credential.return_value)
        credential.assert_called_once_with(
            tenant_id="tenant",
            client_id="client",
            client_secret="secret",
            user_assertion="user-token",
        )


if __name__ == "__main__":
    unittest.main()
