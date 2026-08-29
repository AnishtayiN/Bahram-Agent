"""Tests for security modules."""
import pytest
from bahram.security.file_safety import FileWriteSafety
from bahram.security.tirith import TirithScanner
from bahram.security.pairing import DMPairingManager

class TestFileWriteSafety:
    def test_safety_creation(self):
        safety = FileWriteSafety()
        assert safety is not None

    def test_check_safe_path(self):
        safety = FileWriteSafety()
        safe, msg = safety.check_write("/tmp/test.txt")
        assert isinstance(safe, bool)

class TestTirithScanner:
    def test_scanner_creation(self):
        scanner = TirithScanner()
        assert scanner is not None

    def test_scan_safe_code(self):
        scanner = TirithScanner()
        result = scanner.scan("x = 1\ny = 2")
        assert result.safe is True

    def test_scan_dangerous_code(self):
        scanner = TirithScanner()
        result = scanner.scan("rm -rf /")
        assert result.safe is False

class TestDMPairingManager:
    def test_pairing_creation(self, tmp_path):
        manager = DMPairingManager(data_dir=str(tmp_path))
        assert manager is not None

    def test_generate_code(self, tmp_path):
        manager = DMPairingManager(data_dir=str(tmp_path))
        code = manager.generate_code("telegram", "12345")
        assert code is not None
        assert len(code) > 0

    def test_verify_code(self, tmp_path):
        manager = DMPairingManager(data_dir=str(tmp_path))
        code = manager.generate_code("telegram", "12345")
        result = manager.verify_code(code)
        assert result is not None
