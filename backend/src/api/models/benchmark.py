from pydantic import BaseModel
from pydantic import Field


class BenchmarkScenario(BaseModel):
    scenario_name: str = Field(default="baseline_default")
    duration_seconds: int = Field(default=300, ge=30)
    stream_count: int = Field(default=1, ge=1)
    resolution: str = Field(default="640x360")
    model_name: str = Field(default="yolov8n.pt")
    annotation_enabled: bool = True
    notes: str | None = None


class BenchmarkExportResponse(BaseModel):
    run_id: str
    json_report_path: str
    csv_report_path: str
    scenario_name: str
    streams_count: int


class BenchmarkHistoryItem(BaseModel):
    run_id: str
    created_at: str | None = None
    scenario_name: str
    model_name: str | None = None
    streams_count: int
    json_report_path: str
    csv_report_path: str


class BenchmarkHistoryResponse(BaseModel):
    reports_dir: str
    count: int
    items: list[BenchmarkHistoryItem]
