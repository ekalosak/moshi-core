import asyncio
import os
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCDataChannel
from loguru import logger
from pydantic import BaseModel

from moshi.core.activities import ActivityType
from moshi.core.base import User
from moshi.api.auth import user_profile
from moshi.call import WebRTCAdapter

pcs = set()

CONNECTION_TIMEOUT = int(os.getenv("MOSHICONNECTIONTIMEOUT", 5))
logger.info(f"Using (WebRTC session) CONNECTION_TIMEOUT={CONNECTION_TIMEOUT}")

router = APIRouter()


async def shutdown():
    """Close peer connections."""
    logger.debug(f"Closing {len(pcs)} PeerConnections...")
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)
    pcs.clear()


class Offer(BaseModel):
    sdp: str
    type: str

@logger.catch
@router.post("/call/{activity_type}")
async def new_call(
    offer: Offer,
    activity_type: ActivityType,
    profile: User = Depends(user_profile),
):
    """In WebRTC, there's an initial offer->answer exchange that negotiates the connection parameters.
    This endpoint accepts an offer request from a client and returns an answer with the SDP (session description protocol).
    Moreover, it sets up the PeerConnection (pc) and the event listeners on the connection.
    Sources:
        - RFC 3264
        - RFC 2327
    """
    adapter = WebRTCAdapter(activity_type=activity_type)
    desc = RTCSessionDescription(**offer.model_dump())
    pc = RTCPeerConnection()
    pcs.add(pc)
    logger.trace(f"offer: {offer}")
    logger.trace(f"created peer connection: {pc}")

    @pc.on("datachannel")
    def on_datachannel(dc: RTCDataChannel):
        logger.trace(f"dc: new: {dc.label}:{dc.id}")
        adapter.add_dc(dc)

        @dc.on("message")
        def on_message(msg):
            logger.trace(f"dc: msg: {msg}")
            if isinstance(msg, str) and msg.startswith("ping "):
                # NOTE io under the hood done with fire-and-forget ensure_future, UDP
                dc.send("pong " + msg[4:])
            elif isinstance(msg, str):
                logger.warning(f"dc: msg: unexpected message: {msg}")
            else:
                logger.warning(f"dc: msg: unexpected message type: {type(msg)}")

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        logger.debug(f"Connection state changed to: {pc.connectionState}")
        if pc.connectionState == "failed":
            await pc.close()
            pcs.discard(pc)
        elif pc.connectionState == "connecting":
            try:
                await adapter.start()
            except Exception as e:
                logger.error(f"Exception starting adapter: {e}")
                await pc.close()
                pcs.discard(pc)
        elif pc.connectionState == "connected":
            try:
                await asyncio.wait_for(
                    adapter.wait_dc_connected(), timeout=CONNECTION_TIMEOUT
                )
            except asyncio.TimeoutError as e:
                with logger.contextualize(timeout_sec=CONNECTION_TIMEOUT):
                    logger.error("Timeout waiting for dc connected")

    @pc.on("track")
    def on_track(track):
        logger.info(f"Track {track.kind} received")
        if track.kind != "audio":
            raise TypeError(
                f"Track kind not supported, expected 'audio', got: '{track.kind}'"
            )
        adapter.detector.setTrack(track)  # must be called before start()
        pc.addTrack(adapter.responder.audio)
        logger.success(f"Added audio track: {track.kind}:{track.id}")

        @track.on("ended")
        async def on_ended():  # e.g. user disconnects audio
            logger.debug(f"Track {track.kind} ended, stopping adapter...")
            await adapter.stop()
            logger.debug(f"Adapter stopped.")

    await pc.setRemoteDescription(desc)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)
    logger.trace(f"answer: {answer}")

    return {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
