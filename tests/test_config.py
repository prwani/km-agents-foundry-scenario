import unittest

from km_agents.config import ConfigurationError, parse_allowed_public_ips


class ConfigTests(unittest.TestCase):
    def test_public_ipv4_allow_list_is_parsed(self):
        self.assertEqual(parse_allowed_public_ips("8.8.8.8,1.1.1.1"), ["8.8.8.8", "1.1.1.1"])

    def test_private_ipv4_is_rejected(self):
        with self.assertRaises(ConfigurationError):
            parse_allowed_public_ips("10.0.0.5")

    def test_empty_allow_list_is_rejected(self):
        with self.assertRaises(ConfigurationError):
            parse_allowed_public_ips("")


if __name__ == "__main__":
    unittest.main()
