import pytest
import io
import zipfile
import asyncio
import json
from unittest.mock import patch, MagicMock, AsyncMock

from utils.cv_processor import (
    extract_text_fast,
    extract_pdf_text_fast,
    extract_docx_text_fast,
    validate_cv_files,
    extract_linkedin_zip,
    _process_batch_worker,
    process_cv_batch_parallel,
    CVProcessingCache,
    get_cv_cache,
    process_cv_batch_ultra_fast,
    process_cv_batch,
    process_linkedin_export,
    chunk_list,
    extract_linkedin_zip_streaming,
    process_cv_batch_chunked,
    create_celery_task,
    get_processing_status
)

def test_extract_text_fast_txt():
    # Test txt file extraction
    content = b"Hello world! This is a test CV."
    text = extract_text_fast(content, "test.txt")
    assert "Hello world!" in text

def test_extract_text_fast_fallback():
    # Test unknown extension fallback
    content = b"Plain text content here."
    text = extract_text_fast(content, "test.unknown")
    assert "Plain text content here." in text

@patch("utils.cv_processor.extract_pdf_text_fast")
@patch("utils.cv_processor.extract_docx_text_fast")
def test_extract_text_fast_extensions(mock_docx, mock_pdf):
    mock_pdf.return_value = "PDF text"
    mock_docx.return_value = "DOCX text"
    
    assert extract_text_fast(b"pdf", "test.pdf") == "PDF text"
    assert extract_text_fast(b"docx", "test.docx") == "DOCX text"
    
    # Exception handling
    mock_pdf.side_effect = Exception("PDF error")
    assert extract_text_fast(b"pdf", "test.pdf") == ""

@patch("pdfplumber.open")
def test_extract_pdf_text_fast_success(mock_pdf_open):
    # Mock pdfplumber with 3 pages
    mock_pdf = MagicMock()
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "Page content"
    mock_page.extract_words.return_value = []
    mock_pdf.pages = [mock_page, mock_page, mock_page]
    mock_pdf_open.return_value.__enter__.return_value = mock_pdf
    
    text = extract_pdf_text_fast(b"dummy pdf")
    assert "Page content" in text

@patch("pdfplumber.open")
@patch("main._extract_pdf_text")
@patch("services.pdf_text_extractor.extract_pdf_text")
def test_extract_pdf_text_fast_many_pages(mock_layout_extract, mock_main_extract, mock_pdf_open):
    # Mock pdfplumber with 10 pages
    mock_pdf = MagicMock()
    mock_pdf.pages = [MagicMock()] * 10
    mock_pdf_open.return_value.__enter__.return_value = mock_pdf
    
    mock_layout_extract.return_value = ("", False)
    mock_main_extract.return_value = ("Robust full text", None)
    
    text = extract_pdf_text_fast(b"dummy pdf")
    assert text == "Robust full text"

@patch("pdfplumber.open")
@patch("services.pdf_text_extractor.extract_pdf_text")
def test_extract_pdf_text_fast_fallback_cv_text(mock_layout_extract, mock_pdf_open):
    mock_pdf_open.side_effect = ImportError("No pdfplumber")
    mock_layout_extract.side_effect = ImportError("No pdfplumber")
    text = extract_pdf_text_fast(b"dummy pdf")
    assert text == ""

@patch("pdfplumber.open")
@patch("services.pdf_text_extractor.extract_pdf_text")
def test_extract_pdf_text_fast_exception(mock_layout_extract, mock_pdf_open):
    mock_pdf_open.side_effect = Exception("Crash")
    mock_layout_extract.side_effect = Exception("Crash")
    assert extract_pdf_text_fast(b"dummy pdf") == ""

def test_extract_docx_text_fast_success():
    # We can mock docx.Document
    mock_doc = MagicMock()
    mock_p1 = MagicMock()
    mock_p1.text = "Hello DOCX"
    mock_p2 = MagicMock()
    mock_p2.text = "Second paragraph"
    mock_doc.paragraphs = [mock_p1, mock_p2]
    
    with patch("docx.Document", return_value=mock_doc):
        text = extract_docx_text_fast(b"dummy docx")
        assert "Hello DOCX" in text
        assert "Second paragraph" in text

def test_extract_docx_text_fast_fallback():
    # If docx fails with ImportError
    with patch("docx.Document", side_effect=ImportError("No docx")):
        text = extract_docx_text_fast(b"plain docx")
        assert "plain docx" in text

    # If other exception
    with patch("docx.Document", side_effect=Exception("Read failure")):
        assert extract_docx_text_fast(b"dummy") == ""

def test_validate_cv_files():
    async def _run_test():
        class MockFile:
            def __init__(self, name, size=1000):
                self.filename = name
                self.size = size
 
        files = [
            MockFile("valid.pdf"),
            MockFile("invalid.exe"),
            MockFile("toolarge.pdf", size=10_000_000),
            MockFile(None)
        ]
        
        return await validate_cv_files(files)
        
    errors = asyncio.run(_run_test())
    assert len(errors) == 3
    assert any("Unsupported format" in e for e in errors)
    assert any("too large" in e for e in errors)
    assert any("without filename" in e for e in errors)

def test_extract_linkedin_zip():
    async def _run_test():
        # Create an in-memory zip file
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("test1.pdf", b"pdf content")
            zf.writestr("test2.txt", b"txt content")
            zf.writestr("ignore.exe", b"executable")
        zip_buffer.seek(0)
        
        class MockZipUpload:
            async def read(self):
                return zip_buffer.getvalue()
                
        mock_zip = MockZipUpload()
        return await extract_linkedin_zip(mock_zip)
    
    extracted = asyncio.run(_run_test())
    
    assert len(extracted) == 2
    filenames = [e["filename"] for e in extracted]
    assert "test1.pdf" in filenames
    assert "test2.txt" in filenames

def test_extract_linkedin_zip_error():
    async def _run_test():
        class MockZipUpload:
            async def read(self):
                return b"not a zip file"
        
        return await extract_linkedin_zip(MockZipUpload())
        
    with pytest.raises(ValueError, match="Failed to extract LinkedIn ZIP"):
        asyncio.run(_run_test())

    async def _run_test_empty():
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("ignore.exe", b"executable")
        zip_buffer.seek(0)
        
        class MockZipUpload:
            async def read(self):
                return zip_buffer.getvalue()
        
        return await extract_linkedin_zip(MockZipUpload())
        
    with pytest.raises(ValueError, match="No valid CV files found in ZIP"):
        asyncio.run(_run_test_empty())

@patch("utils.cv_text.extract_structured_data")
@patch("utils.cv_processor.calculate_final_score")
def test_process_batch_worker(mock_calc, mock_extract):
    # Mock the internal logic
    mock_extract.return_value = {"skills": ["Python"], "experience_years": 5}
    mock_calc.return_value = (85.0, 90.0, {"match": "High"})
    
    batch = [
        {
            "filename": "test.txt",
            "content": b"Very long dummy text to ensure it passes the 50 char limit. Very long dummy text to ensure it passes the 50 char limit."
        },
        {
            "filename": "short.txt",
            "content": b"too short"
        }
    ]
    
    job_desc = "Looking for a Python developer"
    job_id = 1
    
    results = _process_batch_worker(batch, job_desc, job_id)
    
    assert len(results) == 2
    
    # Check the successful one
    success = next(r for r in results if r["filename"] == "test.txt")
    assert success["status"] == "success"
    assert success["final_score"] == 85.0
    assert success["ats_score"] == 90.0
    
    # Check the short one
    short = next(r for r in results if r["filename"] == "short.txt")
    assert short["status"] == "error"
    assert "No readable text" in short["error"]

@patch("utils.cv_text.extract_structured_data", side_effect=Exception("Extraction failed"))
def test_process_batch_worker_extraction_failed(mock_extract):
    batch = [
        {
            "filename": "test.txt",
            "content": b"Very long dummy text to ensure it passes the 50 char limit. Very long dummy text to ensure it passes the 50 char limit."
        }
    ]
    results = _process_batch_worker(batch, "Job", 1)
    assert results[0]["status"] == "error"
    assert "Processing failed" in results[0]["error"]

import concurrent.futures

@patch("utils.cv_processor.ProcessPoolExecutor")
@patch("services.batch_persistence.persist_batch_results")
def test_process_cv_batch_parallel(mock_persist, mock_ppe):
    async def _run_test():
        # Setup a dummy executor that just runs the function synchronously
        class DummyExecutor:
            def __enter__(self): return self
            def __exit__(self, exc_type, exc_val, exc_tb): pass
            def submit(self, fn, *args, **kwargs):
                future = concurrent.futures.Future()
                try:
                    future.set_result(fn(*args, **kwargs))
                except Exception as e:
                    future.set_exception(e)
                return future
        
        mock_ppe.return_value = DummyExecutor()
        
        files = [
            {"filename": "test.txt", "content": b"Very long dummy text to pass the limit. Very long dummy text to pass the limit."}
        ]
        
        with patch("utils.cv_processor._process_batch_worker") as mock_worker:
            mock_worker.return_value = [
                {"filename": "test.txt", "final_score": 80.0, "status": "success"}
            ]
            
            # Test simple parallel
            res1 = await process_cv_batch_parallel(files, "Job Desc", 1, workers=1)
            assert len(res1) == 1
            
            # Test empty list
            res_empty = await process_cv_batch_parallel([], "Job Desc", 1)
            assert res_empty == []

            # Test parallel with persist
            res2 = await process_cv_batch_parallel(files, "Job Desc", 1, workers=1, persist=True, org_id=10, recruiter_id=20)
            assert len(res2) == 1
            mock_persist.assert_called_once()
            
    asyncio.run(_run_test())

def test_cv_processing_cache():
    async def _run_test():
        # Memory-only cache test
        cache = CVProcessingCache(memory_cache_size=2)
        
        # Cache miss
        assert await cache.get_cached_score("hash1", 1) is None
        
        # Cache hit
        result = {"status": "success", "final_score": 90.0}
        await cache.cache_score("hash1", 1, result)
        
        cached = await cache.get_cached_score("hash1", 1)
        assert cached is not None
        assert cached["final_score"] == 90.0
        
        # Size limit test
        await cache.cache_score("hash2", 1, result)
        await cache.cache_score("hash3", 1, result) # This shouldn't exceed or might not be saved depending on implementation
        
        # Redis cache test
        mock_redis = AsyncMock()
        mock_redis.get.return_value = json.dumps({"status": "success", "final_score": 85.0})
        cache_redis = CVProcessingCache(redis_client=mock_redis)
        
        cached_redis = await cache_redis.get_cached_score("hash_redis", 2)
        assert cached_redis["final_score"] == 85.0
        mock_redis.get.assert_called_once()
        
        await cache_redis.cache_score("hash_redis", 2, {"score": 85})
        mock_redis.setex.assert_called_once()
        
        # Redis exception check
        mock_redis.get.side_effect = Exception("Redis connection fail")
        mock_redis.setex.side_effect = Exception("Redis set fail")
        cache_redis.memory_cache.clear()
        assert await cache_redis.get_cached_score("hash_redis", 2) is None
        await cache_redis.cache_score("hash_redis", 2, {"score": 85}) # shouldn't throw exception

    asyncio.run(_run_test())

@patch("utils.cv_processor.CVProcessingCache")
def test_get_cv_cache(mock_cache_cls):
    with patch("redis.asyncio.Redis", side_effect=Exception("Redis down")):
        cache = get_cv_cache()
        assert cache is not None

@patch("utils.cv_processor.process_cv_batch_parallel")
@patch("utils.cv_processor.get_cv_cache")
def test_process_cv_batch_ultra_fast(mock_get_cache, mock_parallel):
    async def _run_test():
        mock_cache = AsyncMock()
        mock_get_cache.return_value = mock_cache
        
        # Mock cache hit for file 1, miss for file 2
        import hashlib
        hash_val = hashlib.md5(b"content1").hexdigest()
        mock_cache.get_cached_score.side_effect = lambda h, j: {"final_score": 95.0, "status": "success"} if h == hash_val else None
        
        mock_parallel.return_value = [{"filename": "f2.txt", "final_score": 80.0, "status": "success"}]
        
        files = [
            {"filename": "f1.txt", "content": b"content1"},
            {"filename": "f2.txt", "content": b"content2"}
        ]
        
        # Test empty files
        assert await process_cv_batch_ultra_fast([], "Job", 1) == []
        
        # Run with cache
        results = await process_cv_batch_ultra_fast(files, "Job", 1, use_cache=True)
        assert len(results) == 2
        assert results[0]["final_score"] == 95.0 # Sorts by score descending
        assert results[1]["final_score"] == 80.0
        
        # Run without cache
        mock_parallel.return_value = [
            {"filename": "f1.txt", "final_score": 75.0, "status": "success"},
            {"filename": "f2.txt", "final_score": 80.0, "status": "success"}
        ]
        results_no_cache = await process_cv_batch_ultra_fast(files, "Job", 1, use_cache=False)
        assert len(results_no_cache) == 2
        assert results_no_cache[0]["final_score"] == 80.0

    asyncio.run(_run_test())

@patch("utils.cv_processor.extract_structured")
def test_process_cv_batch_uploadfile(mock_extract):
    async def _run_test():
        # Setup mock fast upload files
        class DummyUploadFile:
            def __init__(self, filename, content):
                self.filename = filename
                self.content = content
            async def read(self):
                return self.content
                
        files = [
            DummyUploadFile("test.txt", b"Very long dummy text to satisfy the 50 char limit requirement. Very long dummy text to satisfy the 50 char limit requirement."),
            DummyUploadFile("short.txt", b"too short"),
            DummyUploadFile("fail.txt", b"throw exception in pipeline. throw exception in pipeline. throw exception in pipeline.")
        ]
        
        def mock_extract_impl(cv_text, job_description, lang):
            if "dummy" in cv_text:
                return {"final_score": 90.0, "ats_score": 85.0}
            raise Exception("Pipeline crashed")
            
        mock_extract.side_effect = mock_extract_impl
        
        results = await process_cv_batch(files, "Job", 1)
        assert len(results) == 3
        
        success = next(r for r in results if r["filename"] == "test.txt")
        assert success["status"] == "success"
        assert success["final_score"] == 90.0
        
        short = next(r for r in results if r["filename"] == "short.txt")
        assert short["status"] == "error"
        assert "Insufficient text" in short["error"]
        
        fail = next(r for r in results if r["filename"] == "fail.txt")
        assert fail["status"] == "error"
        assert "Processing failed" in fail["error"]

    asyncio.run(_run_test())

@patch("utils.cv_processor.extract_linkedin_zip")
@patch("utils.cv_processor.process_cv_batch")
def test_process_linkedin_export(mock_process, mock_extract):
    async def _run_test():
        mock_extract.return_value = [
            {"filename": "test.txt", "content": b"content"}
        ]
        mock_process.return_value = [
            {"filename": "test.txt", "status": "success", "final_score": 85.0}
        ]
        
        res = await process_linkedin_export(MagicMock(), "Job", 1)
        assert len(res) == 1
        assert res[0]["final_score"] == 85.0
        
    asyncio.run(_run_test())

def test_chunk_list():
    items = list(range(10))
    chunks = list(chunk_list(items, chunk_size=3))
    assert len(chunks) == 4
    assert chunks[0] == [0, 1, 2]
    assert chunks[3] == [9]

def test_extract_linkedin_zip_streaming():
    async def _run_test():
        # Create zip with multiple files
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            for i in range(5):
                zf.writestr(f"file_{i}.txt", f"content_{i}".encode())
            zf.writestr("ignore.exe", b"exe")
        zip_buffer.seek(0)
        
        mock_file = AsyncMock()
        mock_file.read.return_value = zip_buffer.getvalue()
        
        generator = extract_linkedin_zip_streaming(mock_file, chunk_size=2)
        chunks = []
        async for chunk in generator:
            chunks.append(chunk)
            
        assert len(chunks) == 3
        assert len(chunks[0]) == 2
        assert len(chunks[2]) == 1

    asyncio.run(_run_test())

@patch("utils.cv_processor.extract_linkedin_zip_streaming")
@patch("utils.cv_processor.process_cv_batch")
def test_process_cv_batch_chunked(mock_process, mock_stream):
    async def _run_test():
        # Mock stream yield chunks
        async def mock_generator(zip_file, chunk_size):
            yield [{"filename": "f1.txt", "content": b"c1"}]
            yield [{"filename": "f2.txt", "content": b"c2"}]
            
        mock_stream.side_effect = mock_generator
        
        # Mock process batch returns
        mock_process.side_effect = [
            [{"filename": "f1.txt", "status": "success", "final_score": 90.0}],
            [{"filename": "f2.txt", "status": "error", "error": "Fail"}]
        ]
        
        callback_calls = []
        async def progress_callback(status):
            callback_calls.append(status)
            
        results, summary = await process_cv_batch_chunked(
            MagicMock(), "Job", 1, chunk_size=1, progress_callback=progress_callback
        )
        
        assert len(results) == 2
        assert summary["total_processed"] == 1
        assert summary["total_errors"] == 1
        assert len(callback_calls) == 2

    asyncio.run(_run_test())

def test_create_celery_task():
    import sys
    # Create mock celery_app module
    mock_celery_app_module = MagicMock()
    mock_celery_instance = MagicMock()
    mock_task = MagicMock()
    mock_task.id = "task_id_123"
    mock_celery_instance.send_task.return_value = mock_task
    mock_celery_app_module.celery_app = mock_celery_instance
    
    sys.modules['celery_app'] = mock_celery_app_module
    
    try:
        res = create_celery_task("batch_id_1", 10, 2)
        assert res["task_id"] == "task_id_123"
        assert res["status"] == "queued"
        
        # Test error case
        mock_celery_instance.send_task.side_effect = Exception("Celery error")
        assert create_celery_task("batch_id_1", 10, 2) is None
    finally:
        # Clean up sys.modules
        if 'celery_app' in sys.modules:
            del sys.modules['celery_app']

@patch("redis.Redis")
def test_get_processing_status(mock_redis):
    async def _run_test():
        # Mock Redis client
        mock_r = MagicMock()
        mock_redis.return_value = mock_r
        
        # Status found
        mock_r.get.return_value = json.dumps({"status": "processing", "processed": 5})
        res1 = await get_processing_status("session_1")
        assert res1["processed"] == 5
        
        # Status not found
        mock_r.get.return_value = None
        res2 = await get_processing_status("session_1")
        assert res2["status"] == "not_found"
        
        # Redis exception
        mock_r.get.side_effect = Exception("Redis connect error")
        res3 = await get_processing_status("session_1")
        assert res3["status"] == "unknown"

    asyncio.run(_run_test())
