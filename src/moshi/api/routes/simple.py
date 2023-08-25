"""This module provides the FastAPI route for the non-WebRTC audio exchange."""
import asyncio
import os

from fastapi import APIRouter, Depends, HTTPException, Request
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCDataChannel
from loguru import logger
from pydantic import BaseModel

# from moshi.core.activities import ActivityType
# from moshi.core.base import User
from moshi.api.auth import user_profile
# from moshi.call import SimpleAdapter

router = APIRouter()

@logger.catch
@router.post("/v1/simple/new/{activity_type}")