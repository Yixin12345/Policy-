"""
Test GetExtractionResult Query Handler

Tests cover:
- Successful extraction result retrieval
- Query validation
- Error handling for missing entities
- Optional data inclusion/exclusion
- Result formatting and data structures
"""
import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock

from backend.application.queries.get_extraction_result import (
    GetExtractionResultQuery,
    GetExtractionResultHandler,
    ExtractionResult,
    TextRegion,
    TableData,
    FormField
)
from backend.domain.entities.page import Page
from backend.domain.entities.job import Job, JobStatus
from backend.domain.exceptions import (
    EntityNotFoundError,
    DomainValidationError,
    RepositoryError
)


class TestGetExtractionResultQuery:
    """Test GetExtractionResultQuery validation"""
    
    def test_valid_query_creation(self):
        """Test creating a valid query"""
        query = GetExtractionResultQuery(
            job_id="job-123",
            page_number=1
        )
        
        assert query.job_id == "job-123"
        assert query.page_number == 1
        assert query.include_raw_data is False
        assert query.include_regions is True
        assert query.include_metadata is True
    
    def test_query_with_options(self):
        """Test creating query with all options"""
        query = GetExtractionResultQuery(
            job_id="job-123",
            page_number=2,
            include_raw_data=True,
            include_regions=False,
            include_metadata=False
        )
        
        assert query.include_raw_data is True
        assert query.include_regions is False
        assert query.include_metadata is False
    
    def test_empty_job_id_raises_error(self):
        """Test that empty job ID raises validation error"""
        with pytest.raises(DomainValidationError, match="Job ID cannot be empty"):
            GetExtractionResultQuery(job_id="", page_number=1)
        
        with pytest.raises(DomainValidationError, match="Job ID cannot be empty"):
            GetExtractionResultQuery(job_id="   ", page_number=1)
    
    def test_invalid_page_number_raises_error(self):
        """Test that invalid page number raises validation error"""
        with pytest.raises(DomainValidationError, match="Page number must be positive"):
            GetExtractionResultQuery(job_id="job-123", page_number=0)
        
        with pytest.raises(DomainValidationError, match="Page number must be positive"):
            GetExtractionResultQuery(job_id="job-123", page_number=-1)


class TestGetExtractionResultHandler:
    """Test GetExtractionResultHandler execution"""
    
    @pytest.fixture
    def mock_job_repository(self):
        """Create mock job repository"""
        return Mock()
    
    @pytest.fixture
    def mock_page_repository(self):
        """Create mock page repository"""
        return Mock()
    
    @pytest.fixture
    def handler(self, mock_job_repository, mock_page_repository):
        """Create handler with mock repositories"""
        return GetExtractionResultHandler(
            job_repository=mock_job_repository,
            page_repository=mock_page_repository
        )
    
    @pytest.fixture
    def sample_job(self):
        """Create sample job entity"""
        job = Mock(spec=Job)
        job.id = "job-123"
        job.name = "Test Job"
        job.status = JobStatus.COMPLETED
        return job
    
    @pytest.fixture
    def sample_page(self):
        """Create sample page entity with extraction data"""
        page = Mock(spec=Page)
        page.job_id = "job-123"
        page.page_number = 1
        page.extracted_text = "Sample extracted text content"
        page.confidence_score = 0.95
        page.created_at = datetime.now()
        
        # Mock structured data
        page.structured_data = {
            'regions': [
                {
                    'text': 'Header Text',
                    'confidence': 0.98,
                    'bbox': {'x': 10, 'y': 10, 'width': 200, 'height': 30},
                    'type': 'paragraph'
                }
            ],
            'tables': [
                {
                    'rows': [['Col1', 'Col2'], ['Val1', 'Val2']],
                    'headers': ['Col1', 'Col2'],
                    'confidence': 0.92,
                    'bbox': {'x': 10, 'y': 50, 'width': 300, 'height': 100}
                }
            ],
            'forms': [
                {
                    'name': 'field1',
                    'value': 'test_value',
                    'type': 'text',
                    'confidence': 0.89,
                    'bbox': {'x': 10, 'y': 200, 'width': 150, 'height': 25}
                }
            ]
        }
        
        # Mock image metadata
        page.image_metadata = {
            'width': 800,
            'height': 1200,
            'dpi': 300
        }
        
        # Mock processing metadata
        page.processing_metadata = {
            'duration_ms': 1500,
            'engine': 'tesseract',
            'engine_version': '5.0.1'
        }
        
        # Mock raw OCR data
        page.raw_ocr_data = {'raw': 'ocr_response_data'}
        
        # Mock error/warning data
        page.processing_errors = []
        page.processing_warnings = ['Low confidence in region 2']
        
        return page
    
    def test_successful_extraction_result_retrieval(
        self, 
        handler, 
        mock_job_repository, 
        mock_page_repository,
        sample_job,
        sample_page
    ):
        """Test successful extraction result retrieval"""
        # Setup mocks
        mock_job_repository.find_by_id.return_value = sample_job
        mock_page_repository.find_page_by_number.return_value = sample_page
        
        # Execute query
        query = GetExtractionResultQuery(job_id="job-123", page_number=1)
        result = handler.handle(query)
        
        # Verify repository calls
        mock_job_repository.find_by_id.assert_called_once_with("job-123")
        mock_page_repository.find_page_by_number.assert_called_once_with("job-123", 1)
        
        # Verify result structure
        assert isinstance(result, ExtractionResult)
        assert result.job_id == "job-123"
        assert result.page_number == 1
        assert result.full_text == "Sample extracted text content"
        assert result.confidence_score == 0.95
        assert result.ocr_engine == "tesseract"
        assert result.ocr_engine_version == "5.0.1"
        assert result.processing_duration_ms == 1500
        
        # Verify image information
        assert result.image_width == 800
        assert result.image_height == 1200
        assert result.image_dpi == 300
        
        # Verify structured data
        assert len(result.text_regions) == 1
        assert result.text_regions[0].text == "Header Text"
        assert result.text_regions[0].confidence == 0.98
        
        assert len(result.tables) == 1
        assert result.tables[0].rows == [['Col1', 'Col2'], ['Val1', 'Val2']]
        assert result.tables[0].headers == ['Col1', 'Col2']
        
        assert len(result.form_fields) == 1
        assert result.form_fields[0].name == "field1"
        assert result.form_fields[0].value == "test_value"
        
        # Verify status information
        assert result.has_errors is False
        assert result.warnings == ['Low confidence in region 2']
    
    def test_extraction_result_with_raw_data(
        self,
        handler,
        mock_job_repository,
        mock_page_repository,
        sample_job,
        sample_page
    ):
        """Test extraction result including raw OCR data"""
        # Setup mocks
        mock_job_repository.find_by_id.return_value = sample_job
        mock_page_repository.find_page_by_number.return_value = sample_page
        
        # Execute query with raw data
        query = GetExtractionResultQuery(
            job_id="job-123",
            page_number=1,
            include_raw_data=True
        )
        result = handler.handle(query)
        
        # Verify raw data is included
        assert result.raw_ocr_response == {'raw': 'ocr_response_data'}
    
    def test_extraction_result_without_regions(
        self,
        handler,
        mock_job_repository,
        mock_page_repository,
        sample_job,
        sample_page
    ):
        """Test extraction result excluding text regions"""
        # Setup mocks
        mock_job_repository.find_by_id.return_value = sample_job
        mock_page_repository.find_page_by_number.return_value = sample_page
        
        # Execute query without regions
        query = GetExtractionResultQuery(
            job_id="job-123",
            page_number=1,
            include_regions=False
        )
        result = handler.handle(query)
        
        # Verify regions are not included
        assert result.text_regions == []
    
    def test_job_not_found_raises_error(
        self,
        handler,
        mock_job_repository,
        mock_page_repository
    ):
        """Test that missing job raises EntityNotFoundError"""
        # Setup mocks
        mock_job_repository.find_by_id.return_value = None
        
        # Execute query
        query = GetExtractionResultQuery(job_id="job-123", page_number=1)
        
        with pytest.raises(EntityNotFoundError, match="Job not found: job-123"):
            handler.handle(query)
        
        # Verify page repository not called
        mock_page_repository.find_page_by_number.assert_not_called()
    
    def test_page_not_found_raises_error(
        self,
        handler,
        mock_job_repository,
        mock_page_repository,
        sample_job
    ):
        """Test that missing page raises EntityNotFoundError"""
        # Setup mocks
        mock_job_repository.find_by_id.return_value = sample_job
        mock_page_repository.find_page_by_number.return_value = None
        
        # Execute query
        query = GetExtractionResultQuery(job_id="job-123", page_number=1)
        
        with pytest.raises(EntityNotFoundError, match="Page 1 not found for job job-123"):
            handler.handle(query)
    
    def test_repository_error_handling(
        self,
        handler,
        mock_job_repository,
        mock_page_repository
    ):
        """Test repository error handling"""
        # Setup mock to raise exception
        mock_job_repository.find_by_id.side_effect = Exception("Database error")
        
        # Execute query
        query = GetExtractionResultQuery(job_id="job-123", page_number=1)
        
        with pytest.raises(RepositoryError, match="Failed to get extraction result"):
            handler.handle(query)


class TestDataStructures:
    """Test extraction result data structures"""
    
    def test_text_region_creation(self):
        """Test TextRegion data structure"""
        region = TextRegion(
            text="Sample text",
            confidence=0.95,
            bounding_box={'x': 10, 'y': 20, 'width': 100, 'height': 30},
            region_type="paragraph"
        )
        
        assert region.text == "Sample text"
        assert region.confidence == 0.95
        assert region.region_type == "paragraph"
    
    def test_table_data_creation(self):
        """Test TableData data structure"""
        table = TableData(
            rows=[['A1', 'B1'], ['A2', 'B2']],
            headers=['Col A', 'Col B'],
            confidence=0.88,
            bounding_box={'x': 0, 'y': 0, 'width': 200, 'height': 50}
        )
        
        assert len(table.rows) == 2
        assert table.headers == ['Col A', 'Col B']
        assert table.confidence == 0.88
    
    def test_form_field_creation(self):
        """Test FormField data structure"""
        field = FormField(
            name="email",
            value="test@example.com",
            field_type="text",
            confidence=0.92,
            bounding_box={'x': 50, 'y': 100, 'width': 150, 'height': 25}
        )
        
        assert field.name == "email"
        assert field.value == "test@example.com"
        assert field.field_type == "text"
        assert field.confidence == 0.92