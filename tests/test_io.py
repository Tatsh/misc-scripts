import os

from pytest_mock import MockerFixture

from tatsh_misc_utils.io import (
    context_os_open,
    unpack_0day,
)

FILE_DESCRIPTOR = 3


def test_context_os_open(mocker: MockerFixture) -> None:
    mock_open = mocker.patch('os.open', return_value=FILE_DESCRIPTOR)
    mock_close = mocker.patch('os.close')
    with context_os_open('test_path', os.O_RDONLY) as fd:
        assert fd == FILE_DESCRIPTOR
        mock_open.assert_called_once_with('test_path', os.O_RDONLY, 511, dir_fd=None)
    mock_close.assert_called_once_with(FILE_DESCRIPTOR)


def test_unpack_0day(mocker: MockerFixture) -> None:
    mock_path = mocker.patch('tatsh_misc_utils.io.Path')
    mocker.patch('tatsh_misc_utils.io.contextlib.chdir')
    mocker.patch('tatsh_misc_utils.io.ZipFile')
    mocker.patch('tatsh_misc_utils.io.crc32').return_value = 0
    mock_zip = mocker.Mock()
    mock_diz = mocker.Mock()
    mock_rar = mocker.Mock()
    mock_rar.name = 'test.rar'
    mock_path.return_value.glob.side_effect = [[mock_zip], [mock_diz], [mock_rar], [mock_rar]]
    unpack_0day('test_path', remove_diz=True)
    mock_diz.unlink.assert_called_once()
    mock_path.return_value.glob.assert_any_call('*.rar')
    mock_path.return_value.glob.assert_any_call('*.[rstuvwxyz][0-9a][0-9r]')
    mock_path.return_value.open.return_value.__enter__.return_value.write.assert_any_call(
        'test.rar 00000000\n')
