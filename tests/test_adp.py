from requests.exceptions import HTTPError
from requests_mock import Mocker
import pytest

from tatsh_misc_utils.adp import SalaryResponse, calculate_salary


def test_salary_response_str() -> None:
    response = SalaryResponse(federal=100.0,
                              fica=50.0,
                              gross=1000.0,
                              medicare=25.0,
                              net_pay=825.0,
                              state=0)
    expected_str = """Gross     \033[1;32m 1000.00\033[0m
Federal   \033[1;32m  100.00\033[0m
FICA      \033[1;32m   50.00\033[0m
Medicare  \033[1;32m   25.00\033[0m
State     \033[1;32m    0.00\033[0m
------------------
Net       \033[1;32m  825.00\033[0m

------------------
Fuckery   \033[1;31m  175.00\033[0m"""
    assert str(response) == expected_str


FEDERAL_TAX = 100.0
FICA_TAX = 50.0
GROSS_PAY = 4900.0
MEDICARE_TAX = 25.0
NET_PAY = 825.0
STATE = 0
FUCKERY = 175.0


def test_calculate_salary_success(requests_mock: Mocker) -> None:
    mock_response = {
        'content': {
            'federal': 100.0,
            'fica': 50.0,
            'medicare': 25.0,
            'netPay': 825.0,
            'state': 0
        }
    }
    requests_mock.post('https://calculators.symmetry.com/api/calculators/hourly?report=none',
                       json=mock_response)
    result = calculate_salary(hours=70, pay_rate=70.0, state='FL')

    assert result.federal == FEDERAL_TAX
    assert result.fica == FICA_TAX
    assert result.medicare == MEDICARE_TAX
    assert result.net_pay == NET_PAY
    assert result.state == STATE
    assert result.gross == GROSS_PAY


def test_calculate_salary_http_error(requests_mock: Mocker) -> None:
    requests_mock.post('https://calculators.symmetry.com/api/calculators/hourly?report=none',
                       status_code=500)
    with pytest.raises(HTTPError):
        calculate_salary(hours=70, pay_rate=70.0, state='FL')
