# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2025 Tobias Brox <tobias@tobix.eu>
#
# This library is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Radicale.  If not, see <http://www.gnu.org/licenses/>.

"""
Tests for pathutils module.

"""

import gc
import os
import tempfile

import pytest

from radicale import pathutils


class TestPathToFilesystem:
    """Tests for path_to_filesystem function."""

    @pytest.mark.filterwarnings("error::ResourceWarning")
    @pytest.mark.filterwarnings("error::pytest.PytestUnraisableExceptionWarning")
    def test_scandir_iterator_closed(self) -> None:
        """Verify that os.scandir iterator is properly closed.

        This test catches ResourceWarning: unclosed scandir iterator
        which occurs when os.scandir() is used without a context manager.
        See: https://github.com/Kozea/Radicale/issues/1972

        The ResourceWarning is emitted during garbage collection when an
        unclosed scandir iterator is finalized. We use pytest.mark.filterwarnings
        to convert both ResourceWarning and PytestUnraisableExceptionWarning
        to errors.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a subdirectory so path_to_filesystem has something
            # to scan (the scandir check is for case-insensitive filesystems)
            subdir = os.path.join(tmpdir, "testdir")
            os.makedirs(subdir)

            # Call path_to_filesystem - if scandir iterator is not closed,
            # a ResourceWarning will be emitted during garbage collection
            result = pathutils.path_to_filesystem(tmpdir, "testdir")
            assert result == subdir

            # Force garbage collection to trigger any ResourceWarning
            # from unclosed iterators
            gc.collect()

    def test_path_to_filesystem_basic(self) -> None:
        """Test basic path_to_filesystem functionality."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Test empty path
            result = pathutils.path_to_filesystem(tmpdir, "")
            assert result == tmpdir

            # Test single component
            subdir = os.path.join(tmpdir, "test")
            os.makedirs(subdir)
            result = pathutils.path_to_filesystem(tmpdir, "test")
            assert result == subdir

            # Test nested path
            nested = os.path.join(subdir, "nested")
            os.makedirs(nested)
            result = pathutils.path_to_filesystem(tmpdir, "test/nested")
            assert result == nested

    def test_unsafe_path_raises(self) -> None:
        """Test that unsafe path components raise UnsafePathError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Hidden files (starting with .) are not safe
            with pytest.raises(pathutils.UnsafePathError):
                pathutils.path_to_filesystem(tmpdir, ".hidden")

            # Backup files (ending with ~) are not safe
            with pytest.raises(pathutils.UnsafePathError):
                pathutils.path_to_filesystem(tmpdir, "backup~")
