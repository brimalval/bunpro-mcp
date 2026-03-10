import asyncio
from typing import Callable, Generator

# pyright: reportMissingImports=false, reportDeprecated=false, reportUnknownMemberType=false, reportUntypedFunctionDecorator=false, reportUnknownParameterType=false, reportUnknownVariableType=false
import pytest

from .utils import ResponseHandler, make_mock_async_client


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_http_client() -> Callable[[ResponseHandler], object]:
    def _factory(handler: ResponseHandler):
        return make_mock_async_client(handler)

    return _factory
