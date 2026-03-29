from unittest.mock import patch

import pytest

from nixsearch.check_dependencies import check_dependencies
from nixsearch.exceptions import MissingDependencyError


def test_all_found():
    with patch("nixsearch.check_dependencies.shutil.which", return_value="/usr/bin/nix"):
        check_dependencies()


def test_missing_command():
    with patch("nixsearch.check_dependencies.shutil.which", return_value=None):
        with pytest.raises(MissingDependencyError, match="missing required commands"):
            check_dependencies()
