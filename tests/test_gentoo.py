from unittest.mock import Mock

from pytest_mock import MockerFixture
import pytest

from tatsh_misc_utils.gentoo import InvalidActiveKernelSourcePath, clean_old_kernels_and_modules


@pytest.fixture
def mock_path(mocker: MockerFixture) -> Mock:
    return mocker.patch('tatsh_misc_utils.gentoo.Path')


@pytest.fixture
def mock_rmtree(mocker: MockerFixture) -> Mock:
    return mocker.patch('tatsh_misc_utils.gentoo.rmtree')


def test_clean_old_kernels_and_modules_success(mock_path: Mock, mock_rmtree: Mock,
                                               mocker: MockerFixture) -> None:
    mock_loc = mock_path.return_value.__truediv__.return_value
    mock_loc.exists.return_value = True
    mock_loc.is_symlink.return_value = True
    mock_loc.readlink.return_value = 'linux-5.10.0'

    mock_module_dir = mocker.MagicMock()
    mock_module_dir.is_dir.return_value = True
    mock_module_dir.__str__.return_value = 'module-1'

    mock_kernel_dir = mocker.MagicMock()
    mock_kernel_dir.is_dir.return_value = True
    mock_kernel_dir.__str__.return_value = 'linux-5.9.0'

    mock_path.return_value.glob.side_effect = [[mock_module_dir], [mock_kernel_dir]]

    result = list(clean_old_kernels_and_modules())
    assert result == ['module-1', 'linux-5.9.0']
    mock_rmtree.assert_any_call(mock_module_dir)
    mock_rmtree.assert_any_call(mock_kernel_dir)


def test_clean_old_kernels_and_modules_no_symlink(mock_path: Mock) -> None:
    mock_loc = mock_path.return_value.__truediv__.return_value
    mock_loc.exists.return_value = True
    mock_loc.is_symlink.return_value = False

    with pytest.raises(InvalidActiveKernelSourcePath):
        list(clean_old_kernels_and_modules())


def test_clean_old_kernels_and_modules_file_not_found(mock_path: Mock) -> None:
    mock_loc = mock_path.return_value.__truediv__.return_value
    mock_loc.exists.return_value = False

    with pytest.raises(FileNotFoundError):
        list(clean_old_kernels_and_modules())
