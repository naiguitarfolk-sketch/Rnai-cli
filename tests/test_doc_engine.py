# -*- coding: utf-8 -*-
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rnai_cli import config as cfg
from rnai_cli import doc_engine
from rnai_cli import tools


class TestDocEngine(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.workspace_dir = Path(self.temp_dir) / "workspace"
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.patcher_ws = patch.object(cfg, "get", lambda k: str(self.workspace_dir) if k == "WORKSPACE_DIR" else "")
        self.patcher_ws.start()

    def tearDown(self):
        self.patcher_ws.stop()
        shutil.rmtree(self.temp_dir)

    def test_calculate_basic_math(self):
        r1 = doc_engine.calculate("10 + 5 * 2")
        self.assertTrue(r1["ok"])
        self.assertEqual(r1["result"], 20.0)
        self.assertEqual(r1["formatted"], "20")

        r2 = doc_engine.calculate("(100 - 25) / 3")
        self.assertTrue(r2["ok"])
        self.assertEqual(r2["result"], 25.0)

        r3 = doc_engine.calculate("2 ** 8")
        self.assertTrue(r3["ok"])
        self.assertEqual(r3["result"], 256.0)

    def test_calculate_math_functions(self):
        r = doc_engine.calculate("sqrt(144) + abs(-10)")
        self.assertTrue(r["ok"])
        self.assertEqual(r["result"], 22.0)

    def test_calculate_statistics(self):
        r_mean = doc_engine.calculate("mean([10, 20, 30, 40, 50])")
        self.assertTrue(r_mean["ok"])
        self.assertEqual(r_mean["result"], 30.0)

        r_sum = doc_engine.calculate("sum([1500, 2500, 3500])")
        self.assertTrue(r_sum["ok"])
        self.assertEqual(r_sum["result"], 7500.0)

        r_median = doc_engine.calculate("median([1, 5, 2, 8, 7])")
        self.assertTrue(r_median["ok"])
        self.assertEqual(r_median["result"], 5.0)

    def test_calculate_growth_and_percentage(self):
        # 100 to 150 is 50% growth
        r_growth = doc_engine.calculate("growth(100, 150)")
        self.assertTrue(r_growth["ok"])
        self.assertEqual(r_growth["result"], 50.0)

        # 45 out of 200 is 22.5%
        r_pct = doc_engine.calculate("pct(45, 200)")
        self.assertTrue(r_pct["ok"])
        self.assertEqual(r_pct["result"], 22.5)

    def test_calculate_zero_division(self):
        r = doc_engine.calculate("10 / 0")
        self.assertFalse(r["ok"])
        self.assertIn("หารด้วยศูนย์", r["error"])

    def test_calculate_unsafe_rejection(self):
        r = doc_engine.calculate("__import__('os').system('ls')")
        self.assertFalse(r["ok"])

    def test_extract_plain_text(self):
        f = self.workspace_dir / "sample.txt"
        f.write_text("นี่คือรายงานสรุปประจำเดือน ตุลาคม 2026\nยอดขายรวม 1,500,000 บาท", encoding="utf-8")

        res = doc_engine.extract_document_text(f)
        self.assertTrue(res["ok"])
        self.assertIn("รายงานสรุปประจำเดือน", res["text"])
        self.assertEqual(res["file_name"], "sample.txt")

    def test_extract_csv_and_statistics(self):
        csv_file = self.workspace_dir / "sales.csv"
        csv_content = "Product,Price,Quantity\nApple,50,100\nBanana,20,250\nOrange,35,150\n"
        csv_file.write_text(csv_content, encoding="utf-8")

        res = doc_engine.extract_document_text(csv_file)
        self.assertTrue(res["ok"])
        self.assertIn("### ไฟล์ข้อมูลตาราง: sales.csv", res["text"])
        self.assertIn("Apple", res["text"])
        self.assertIn("Price", res["text"])
        # Columns Price and Quantity should have statistics
        self.assertIn("สรุปข้อมูลสถิติและการคำนวณเบื้องต้น", res["text"])

    def test_save_list_delete_document(self):
        # Test save
        doc_data = "Hello World! Data Analysis Document".encode("utf-8")
        save_res = doc_engine.save_uploaded_document("test_doc.txt", doc_data, target_subfolder="documents")
        self.assertTrue(save_res["ok"])
        self.assertEqual(save_res["name"], "test_doc.txt")
        self.assertEqual(save_res["relative_path"], "documents/test_doc.txt")

        # Test list
        docs = doc_engine.list_documents()
        self.assertGreaterEqual(len(docs), 1)
        doc_names = [d["name"] for d in docs]
        self.assertIn("test_doc.txt", doc_names)

        # Test delete
        del_ok = doc_engine.delete_document("documents/test_doc.txt")
        self.assertTrue(del_ok)
        docs_after = doc_engine.list_documents()
        self.assertNotIn("test_doc.txt", [d["name"] for d in docs_after])


class TestToolsIntegration(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.workspace_dir = Path(self.temp_dir) / "workspace"
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.patcher_ws = patch.object(cfg, "get", lambda k: str(self.workspace_dir) if k == "WORKSPACE_DIR" else "")
        self.patcher_ws.start()

    def tearDown(self):
        self.patcher_ws.stop()
        shutil.rmtree(self.temp_dir)

    def test_tool_schemas_has_doc_and_calc(self):
        names = [t["function"]["name"] for t in tools.TOOL_SCHEMAS]
        self.assertIn("read_document", names)
        self.assertIn("calculate", names)

    def test_execute_calculate(self):
        res = tools.execute("calculate", {"expression": "sum([100, 200, 300])"})
        self.assertIn("OK:", res)
        self.assertIn("600", res)

    def test_execute_read_document(self):
        doc = self.workspace_dir / "research_doc.txt"
        doc.write_text("ผลการทดสอบระบบตัวแทนปัญญาประดิษฐ์", encoding="utf-8")

        res = tools.execute("read_document", {"path": "research_doc.txt"})
        self.assertIn("ผลการทดสอบระบบตัวแทนปัญญาประดิษฐ์", res)


class TestUiEndpoints(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.workspace_dir = Path(self.temp_dir) / "workspace"
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.patcher_ws = patch.object(cfg, "get", lambda k: str(self.workspace_dir) if k == "WORKSPACE_DIR" else "")
        self.patcher_ws.start()

    def tearDown(self):
        self.patcher_ws.stop()
        shutil.rmtree(self.temp_dir)

    def test_upload_and_preview_workflow(self):
        import base64
        # 1. Base64 payload upload
        raw_text = "รายงานวิจัยเรื่องการเรียนรู้ด้วยตนเอง\nกลุ่มตัวอย่าง: 120 คน\nคะแนนเฉลี่ย: 82.5%"
        encoded = base64.b64encode(raw_text.encode("utf-8")).decode("utf-8")
        
        saved = doc_engine.save_uploaded_document("self_study_report.txt", base64.b64decode(encoded), target_subfolder="documents")
        self.assertTrue(saved["ok"])
        self.assertEqual(saved["name"], "self_study_report.txt")

        # 2. Preview
        prev = doc_engine.extract_document_text(saved["relative_path"])
        self.assertTrue(prev["ok"])
        self.assertIn("รายงานวิจัยเรื่องการเรียนรู้ด้วยตนเอง", prev["text"])
        self.assertIn("82.5%", prev["text"])

        # 3. Calculation
        calc = doc_engine.calculate("82.5 * 1.1")
        self.assertTrue(calc["ok"])
        self.assertAlmostEqual(calc["result"], 90.75)

        # 4. List
        docs = doc_engine.list_documents()
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]["name"], "self_study_report.txt")

        # 5. Delete
        deleted = doc_engine.delete_document(saved["relative_path"])
        self.assertTrue(deleted)
        self.assertEqual(len(doc_engine.list_documents()), 0)


class TestStudentUiEndpoints(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.workspace_dir = Path(self.temp_dir) / "workspace"
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.patcher_ws = patch.object(cfg, "get", lambda k: str(self.workspace_dir) if k == "WORKSPACE_DIR" else "")
        self.patcher_ws.start()

    def tearDown(self):
        self.patcher_ws.stop()
        shutil.rmtree(self.temp_dir)

    def test_student_document_upload_and_context(self):
        import base64
        # 1. Student uploads course material
        mat_text = "ชุดวิชาการวิจัย: บทที่ 1 ความหมายและระเบียบวิธีวิจัย\nสูตรประชากร: N = 1000\nกลุ่มตัวอย่าง: n = 280"
        b64 = base64.b64encode(mat_text.encode("utf-8")).decode("utf-8")

        res = doc_engine.save_uploaded_document("unit1_research.txt", base64.b64decode(b64), target_subfolder="documents")
        self.assertTrue(res["ok"])

        # 2. Check document is listed
        docs = doc_engine.list_documents()
        self.assertTrue(any(d["name"] == "unit1_research.txt" for d in docs))

        # 3. Simulate message containing document reference
        text = "ช่วยสรุปเอกสาร unit1_research.txt และคำนวณสัดส่วนกลุ่มตัวอย่าง"
        matched = [d for d in docs if d["name"] in text]
        self.assertEqual(len(matched), 1)

        extracted = doc_engine.extract_document_text(matched[0]["relative_path"])
        self.assertTrue(extracted["ok"])
        self.assertIn("สูตรประชากร", extracted["text"])

        # 4. Calculation for student: 280 / 1000 * 100
        calc = doc_engine.calculate("pct(280, 1000)")
        self.assertTrue(calc["ok"])
        self.assertEqual(calc["result"], 28.0)


