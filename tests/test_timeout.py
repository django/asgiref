import asyncio

import pytest
from packaging.version import Version

import asgiref
from asgiref.timeout import timeout


@pytest.mark.asyncio
async def test_timeout_is_deprecated() -> None:
    with pytest.warns(DeprecationWarning, match="asyncio.timeout"):
        cm = timeout(1)

    # Still functional whilst deprecated.
    async with cm:
        await asyncio.sleep(0)
    assert cm.expired is False

    # Review removal of asgiref.timeout.timeout.
    assert Version(asgiref.__version__) < Version("3.14")
