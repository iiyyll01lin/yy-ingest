from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Any, Optional, Dict, List, Union, Tuple
from enum import Enum


class ChunkMethod(str, Enum):
    FIXED_TOKEN = "fixed_token"
    RECURSIVE_TOKEN = "recursive_token"
    KAMRADT = "kamradt"
    CLUSTER_SEMANTIC = "cluster_semantic"
    LLM_SEMANTIC = "llm_semantic"
    LANGCHAIN_MARKDOWN = "markdown"


# ref: https://github.com/openai/tiktoken/blob/4560a8896f5fb1d35c6f8fd6eee0399f9a1a27ca/tiktoken_ext/openai_public.py#L75
class EncodingMethod(str, Enum):
    CL100K_BASE = "cl100k_base"
    O200K_BASE = "o200k_base"
    P50K_BASE = "p50k_base"
    R50K_BASE = "r50k_base"  # aka gpt2
    GPT2 = "gpt2"
    P50K_EDIT = "p50k_edit"


class RequestData(BaseModel):
    url: str = Field(..., description="API endpoint")
    chunk_method: List[ChunkMethod] = Field(
        [ChunkMethod.LANGCHAIN_MARKDOWN], description="list of chunk methods to apply"
    )
    chunk_max_size: int = Field(
        5100,
        description="max size of chunks (used by cluster_semantic)",
        gt=1700,
        le=6800,
        alias="max_chunk_size",
    )
    start_page: int = Field(1, description="start page", ge=1)
    # if end_page is None, means start page to last page
    end_page: Optional[int] = Field(None, description="end page")
    chunk_size: int = Field(
        2100,
        description="chunk size for tokenization (used by fixed_token, recursive_token)",
        gt=0,
        le=6800,
    )
    chunk_overlap: int = Field(
        1700,
        description="overlap between chunks (used by fixed_token, recursive_token)",
        ge=0,
        le=5100,
    )
    avg_chunk_size: int = Field(
        5100, description="average chunk size target (used by kamradt)", gt=800, le=6800
    )
    encoding_name: EncodingMethod = Field(
        EncodingMethod.CL100K_BASE,
        description="tokenizer encoding name (used by fixed_token)",
    )
    # LANGCHAIN_MARKDOWN
    headers_to_split_on: Optional[List[Tuple[str, str]]] = Field(
        None,
        description="Optional headers to split on for Markdown splitter (e.g., [('#', 'H1'), ('##', 'H2')])",
    )
    return_each_line: bool = Field(
        False, description="Return each line as a separate chunk for Markdown splitter"
    )
    strip_headers: bool = Field(
        False, description="Strip header lines from chunks for Markdown splitter"
    )

    @model_validator(mode="after")
    def validate_required_fields_by_method(self) -> "RequestData":
        """Validate that required fields are present based on chunk methods."""
        methods = self.chunk_method
        if not methods:
            return self  # No methods provided, skip validation

        method_requirements = {
            ChunkMethod.FIXED_TOKEN: {
                "required": ["chunk_size", "chunk_overlap", "encoding_name"],
                "validation": [],
            },
            ChunkMethod.RECURSIVE_TOKEN: {
                "required": ["chunk_size", "chunk_overlap"],
                "validation": [],
            },
            ChunkMethod.KAMRADT: {"required": ["avg_chunk_size"], "validation": []},
            ChunkMethod.CLUSTER_SEMANTIC: {
                "required": ["chunk_max_size"],
                "validation": [
                    lambda model: model.chunk_max_size >= 2100
                    or ValueError(
                        "For cluster_semantic method, chunk_max_size cannot be less than 2100"
                    )
                ],
            },
            # Add LANGCHAIN_MARKDOWN - no specific required fields beyond the optional ones
            ChunkMethod.LANGCHAIN_MARKDOWN: {
                "required": [],  # No fields are strictly required beyond the optional ones
                "validation": [],
            },
            # TODO: Uncomment when ready
            # ChunkMethod.LLM_SEMANTIC: {
            #     "required": [],
            #     "validation": []
            # }
        }

        # Collect all required fields and validations from all methods
        all_required_fields = set()
        all_validations = []

        for method in methods:
            if method in method_requirements:
                requirements = method_requirements[method]
                all_required_fields.update(requirements["required"])
                all_validations.extend(requirements["validation"])

        # Check for required fields
        for field in all_required_fields:
            # Check if the attribute exists and is not None
            # Using getattr with a default doesn't work well for required fields
            if not hasattr(self, field) or getattr(self, field) is None:
                # Handle alias for chunk_max_size
                field_name_for_error = (
                    "max_chunk_size" if field == "chunk_max_size" else field
                )
                raise ValueError(
                    f"Field '{field_name_for_error}' is required for the selected chunk methods"
                )

        # Run all validations
        for validation in all_validations:
            result = validation(self)
            if isinstance(result, ValueError):
                raise result

        return self

    @field_validator("chunk_method")
    def validate_chunk_method_not_empty(cls, v):
        if not v:
            raise ValueError("At least one chunk method must be provided")
        return v

    @field_validator("end_page")
    def end_page_must_be_greater_than_start(cls, v, info):
        start_page = info.data.get("start_page")
        if v is not None and start_page is not None and v < start_page:
            raise ValueError("end_page must be greater than or equal to start_page")
        return v

    @field_validator("chunk_overlap")
    def chunk_overlap_must_be_less_than_chunk_size(cls, v, info):
        chunk_size = info.data.get("chunk_size")
        if chunk_size is not None and v >= chunk_size:
            raise ValueError("chunk_overlap must be less than chunk_size")
        return v

    @field_validator("url")
    def validate_url(cls, v):
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v

    class Config:
        validate_by_name = True  # Pydantic v2


class ResponseData(BaseModel):
    state: bool = Field(True, description="state code")
    msg: str = Field("success", description="error message")
    data: Any = Field(None, description="data or log")
    # duration: Any = Field(None, description="time")

    @field_validator("data")
    def validate_data(cls, v):
        if not isinstance(v, (dict, list, str, type(None))):
            raise ValueError("data must be a dict, list, str, or None")
        return v
