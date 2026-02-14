"""
IP Camera Discovery Service.

Uses standard packages:
- zeroconf: mDNS/Bonjour discovery for RTSP services
- wsdiscovery: WS-Discovery protocol for ONVIF devices
- onvif-zeep-async: ONVIF client to retrieve stream URIs
"""

import asyncio
import logging
import socket
import time
from collections.abc import Iterable
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class DiscoveryService:
    """Discovers IP cameras on the local network using mDNS and ONVIF."""

    def __init__(self):
        self._mdns_service_types = ["_rtsp._tcp.local.", "_onvif._tcp.local."]

    async def scan(self, protocol: str = "mdns", timeout: float = 3.0) -> list[dict]:
        """
        Scan for IP cameras on the network.

        Args:
            protocol: "mdns", "onvif", or "both"
            timeout: Discovery timeout in seconds

        Returns:
            List of discovered cameras with ip, name, rtsp_url, protocol
        """
        protocol = protocol.lower()
        if protocol not in {"mdns", "onvif", "both"}:
            raise ValueError("protocol must be one of: mdns, onvif, both")

        results: list[dict] = []

        if protocol in {"mdns", "both"}:
            mdns_results = await asyncio.to_thread(self._scan_mdns, timeout)
            results.extend(mdns_results)

        if protocol in {"onvif", "both"}:
            onvif_results = await self._scan_onvif_async(timeout)
            results.extend(onvif_results)

        return self._dedupe(results)

    def _scan_mdns(self, timeout: float) -> list[dict]:
        """Scan for cameras using mDNS/Zeroconf."""
        try:
            from zeroconf import ServiceBrowser
            from zeroconf import ServiceListener
            from zeroconf import Zeroconf
        except ImportError as exc:
            raise RuntimeError("zeroconf package is required for mDNS discovery") from exc

        class MdnsListener(ServiceListener):
            def __init__(self):
                self.results: list[dict] = []

            def add_service(self, zeroconf: Zeroconf, service_type: str, name: str):
                info = zeroconf.get_service_info(service_type, name)
                if not info:
                    return
                addresses = [socket.inet_ntoa(addr) for addr in info.addresses]
                for address in addresses:
                    rtsp_url = None
                    if service_type.startswith("_rtsp"):
                        rtsp_url = f"rtsp://{address}:{info.port}/"
                    self.results.append(
                        {
                            "ip": address,
                            "name": info.name.split(".")[0] if info.name else None,
                            "rtsp_url": rtsp_url,
                            "protocol": "mdns",
                        }
                    )

            def update_service(self, zeroconf: Zeroconf, service_type: str, name: str):
                pass

            def remove_service(self, zeroconf: Zeroconf, service_type: str, name: str):
                pass

        zeroconf = Zeroconf()
        listener = MdnsListener()
        browsers = [ServiceBrowser(zeroconf, svc_type, listener) for svc_type in self._mdns_service_types]
        try:
            time.sleep(timeout)
        finally:
            for browser in browsers:
                browser.cancel()
            zeroconf.close()

        return listener.results

    async def _scan_onvif_async(self, timeout: float) -> list[dict]:
        """Scan for ONVIF cameras using WS-Discovery."""
        try:
            from wsdiscovery.discovery import ThreadedWSDiscovery
        except ImportError as exc:
            raise RuntimeError("wsdiscovery package is required for ONVIF discovery") from exc

        results: list[dict] = []

        # Use wsdiscovery for WS-Discovery protocol
        wsd = ThreadedWSDiscovery()
        wsd.start()

        try:
            # Search for ONVIF NetworkVideoTransmitter devices
            services = await asyncio.to_thread(
                wsd.searchServices,
                types=["dn:NetworkVideoTransmitter"],
                timeout=int(timeout),
            )

            for service in services:
                xaddrs = service.getXAddrs()
                scopes = service.getScopes()

                # Extract name from scopes
                name = self._extract_name_from_scopes(scopes)

                for xaddr in xaddrs:
                    parsed = urlparse(xaddr)
                    if not parsed.hostname:
                        continue

                    # Try to get RTSP URL from the ONVIF device
                    rtsp_url = await self._get_onvif_stream_url(
                        parsed.hostname,
                        parsed.port or 80,
                    )

                    results.append(
                        {
                            "ip": parsed.hostname,
                            "name": name,
                            "rtsp_url": rtsp_url,
                            "protocol": "onvif",
                            "onvif_url": xaddr,
                        }
                    )
        except Exception as e:
            logger.warning(f"ONVIF WS-Discovery error: {e}")
        finally:
            wsd.stop()

        return results

    async def _get_onvif_stream_url(
        self,
        host: str,
        port: int,
        username: str = "admin",
        password: str = "admin",
    ) -> str | None:
        """
        Try to get the RTSP stream URL from an ONVIF device.

        Uses onvif-zeep-async to query the device's media service.
        Falls back to common RTSP URL patterns if auth fails.
        """
        try:
            from onvif import ONVIFCamera
        except ImportError:
            logger.debug("onvif-zeep-async not available, skipping stream URL retrieval")
            return self._guess_rtsp_url(host)

        try:
            # Try to connect with default credentials
            camera = ONVIFCamera(host, port, username, password)
            await camera.update_xaddrs()

            media_service = await camera.create_media_service()
            profiles = await media_service.GetProfiles()

            if profiles:
                # Get stream URI for the first profile
                stream_setup = {
                    "Stream": "RTP-Unicast",
                    "Transport": {"Protocol": "RTSP"},
                }
                uri_response = await media_service.GetStreamUri(
                    {
                        "StreamSetup": stream_setup,
                        "ProfileToken": profiles[0].token,
                    }
                )
                return uri_response.Uri

        except Exception as e:
            logger.debug(f"Could not get ONVIF stream URI from {host}: {e}")

        # Fall back to common RTSP URL patterns
        return self._guess_rtsp_url(host)

    @staticmethod
    def _guess_rtsp_url(host: str) -> str:
        """Return a common RTSP URL pattern as fallback."""
        # Common patterns for various camera brands
        return f"rtsp://{host}:554/stream1"

    @staticmethod
    def _extract_name_from_scopes(scopes: list) -> str | None:
        """Extract device name from ONVIF scopes."""
        if not scopes:
            return None

        for scope in scopes:
            scope_str = str(scope)
            if "onvif://www.onvif.org/name/" in scope_str:
                name_part = scope_str.split("onvif://www.onvif.org/name/")[-1]
                from urllib.parse import unquote

                return unquote(name_part)
        return None

    @staticmethod
    def _dedupe(results: Iterable[dict]) -> list[dict]:
        """Remove duplicate camera entries."""
        seen: dict[str, dict] = {}
        for item in results:
            key = item.get("ip", "")
            # Keep the one with more info (prefer ONVIF with URL over mDNS without)
            existing = seen.get(key)
            if not existing or (item.get("rtsp_url") and not existing.get("rtsp_url")):
                seen[key] = item
        return list(seen.values())
