"""管理后台共享 Pydantic schema。"""

from pydantic import BaseModel, Field


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    status: str


class WorkspaceBrief(BaseModel):
    id: int
    name: str


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class ChangePasswordIn(BaseModel):
    old_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class UserCreateIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    role: str = Field(default="user", pattern="^(admin|user)$")


class UserPatchIn(BaseModel):
    role: str | None = Field(default=None, pattern="^(admin|user)$")
    status: str | None = Field(default=None, pattern="^(active|disabled)$")


class ResetPasswordIn(BaseModel):
    new_password: str = Field(min_length=8, max_length=128)


class TaskOut(BaseModel):
    task_id: int
    type: str
    status: str
    progress: float
    result: dict | None = None
    error: str | None = None


class WorkspaceCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    context_config: dict | None = None


class WorkspacePatchIn(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    context_config: dict | None = None


class WorkspaceOut(BaseModel):
    id: int
    name: str
    owner_id: int
    context_config: dict | None
    cwd_repo_id: int | None


class RepoBrief(BaseModel):
    id: int
    url: str
    clone_status: str


class ChatBrief(BaseModel):
    id: int
    app_id: str
    chat_name: str | None


class ChatCheckIn(BaseModel):
    app_id: str = Field(min_length=1, max_length=64)
    chat_id: str = Field(min_length=1, max_length=64)  # 飞书原始群 ID（oc_xxx）


class ChatOut(BaseModel):
    id: int
    app_id: str
    chat_id: str
    chat_name: str | None
    workspace_id: int


class SkillMountIn(BaseModel):
    skill_id: int


class McpMountIn(BaseModel):
    mcp_id: int


class SkillBrief(BaseModel):
    id: int
    name: str
    description: str


class McpBrief(BaseModel):
    id: int
    name: str
    type: str


class WorkspaceDetail(WorkspaceOut):
    repos: list[RepoBrief]
    chats: list[ChatBrief]
    skills: list[SkillBrief]
    mcps: list[McpBrief]


class McpCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    type: str = Field(pattern="^(stdio|http)$")
    config: dict
    visibility: str = Field(default="private", pattern="^(private|public)$")
    read_only: bool = False


class McpPatchIn(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    config: dict | None = None
    visibility: str | None = Field(default=None, pattern="^(private|public)$")
    read_only: bool | None = None


class McpOut(BaseModel):
    id: int
    name: str
    type: str
    config: dict
    owner_id: int
    visibility: str
    read_only: bool


class FeishuAppCreateIn(BaseModel):
    app_id: str = Field(min_length=1, max_length=64)
    app_secret: str = Field(min_length=1, max_length=256)
    name: str = Field(min_length=1, max_length=128)


class FeishuAppPatchIn(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    app_secret: str | None = Field(default=None, max_length=256)


class FeishuAppOut(BaseModel):
    id: int
    app_id: str
    app_secret_masked: str
    name: str
    owner_id: int
    connection_status: str


class AgentMdIn(BaseModel):
    content: str = ""


class MemoryFileIn(BaseModel):
    content: str = ""


class RepoCreateIn(BaseModel):
    url: str = Field(min_length=1, max_length=1024)
    token: str | None = Field(default=None, max_length=512)


class RepoOut(BaseModel):
    id: int
    url: str
    clone_status: str
    local_path: str | None
    last_error: str | None


class SkillOut(BaseModel):
    id: int
    name: str
    description: str
    owner_id: int
    visibility: str
    dir_path: str


class SkillPatchIn(BaseModel):
    description: str | None = Field(default=None, max_length=512)
    visibility: str | None = Field(default=None, pattern="^(private|public)$")


class RunOut(BaseModel):
    id: int
    session_id: int
    feishu_chat_id: int
    status: str
    trigger_message_id: str | None = None
    error: str | None = None
