import unittest
from unittest.mock import Mock, patch

from app.services.risk_score import check_defaulter


class DefaulterTest(unittest.TestCase):
    @patch("app.services.risk_score.requests.get")
    def test_lookup_has_timeout_and_parses_table(self, get):
        get.return_value = Mock(
            text="<table><tr><th>이름</th></tr><tr><td>홍길동</td></tr></table>"
        )

        self.assertTrue(check_defaulter("홍길동"))
        get.assert_called_once_with(
            "https://www.molit.go.kr/USR/WPGE0201/m_37180/DTL.jsp", timeout=5
        )


if __name__ == "__main__":
    unittest.main()
