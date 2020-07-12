import arsenic
from arsenic.errors import SessionStartError
import abc
from functools import partial
import asyncio
import re
import attr
import sys
from distutils.version import StrictVersion
import aiohttp
import os
import structlog


class SilentLogger(structlog.PrintLogger):

    def __init__(self):
        super().__init__(file=open(os.devnull, 'w'))


class PyrWebDriver(arsenic.webdriver.WebDriver):

    async def new_session(self, browser, bind=""):
        status, response = await self.connection.request(
            url="/session",
            method="POST",
            data={"capabilities": {"alwaysMatch": browser.capabilities}},
        )
        original_response = response
        if "sessionId" not in response:
            response = response["value"]
        if "sessionId" not in response:
            if "error" in original_response:
                err_resp = original_response
            elif "error" in response:
                err_resp = response
            else:
                raise SessionStartError("Unknown", "Unknown",
                                        original_response)
            raise SessionStartError(err_resp["error"],
                                    err_resp.get("message", ""),
                                    original_response)
        session_id = response["sessionId"]
        session = browser.session_class(
            connection=self.connection.prefixed(f"/session/{session_id}"),
            bind=bind,
            wait=self.wait,
            driver=self,
            browser=browser,
        )
        session._check_response_error(status, response)
        return session


async def pyr_subprocess_based_service(cmd, service_url, log_file):
    closers = []
    try:
        impl = arsenic.subprocess.get_subprocess_impl()
        process = await impl.start_process(cmd, log_file)
        closers.append(partial(impl.stop_process, process))
        session = aiohttp.ClientSession()
        closers.append(session.close)
        count = 0
        while True:
            try:
                if await arsenic.services.tasked(
                        arsenic.services.check_service_status(session,
                                                              service_url)):
                    break
            except:
                # TODO: make this better
                count += 1
                if count > 30:
                    raise Exception("not starting?")
                await asyncio.sleep(0.5)
        return PyrWebDriver(arsenic.connection.Connection(session,
                                                          service_url),
                            closers)
    except:
        for closer in reversed(closers):
            await closer()
        raise


class PyrService(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def start(self):
        raise NotImplementedError()


class PyrFirefox(arsenic.browsers.Firefox):
    pass


@attr.s
class PyrGeckodriver(PyrService):
    log_file = attr.ib(default=os.devnull)
    binary = attr.ib(default="geckodriver")
    version_check = attr.ib(default=True)

    structlog.configure(logger_factory=SilentLogger)

    _version_re = re.compile(r"geckodriver (\d+\.\d+)")

    async def _check_version(self):
        if self.version_check:
            impl = arsenic.subprocess.get_subprocess_impl()
            output = await impl.run_process([self.binary, "--version"])
            match = self._version_re.search(output)
            if not match:
                raise ValueError(
                    "Could not determine version of geckodriver. To "
                    "disable version checking, set `version_check` to "
                    "`False`."
                )
            version_str = match.group(1)
            version = StrictVersion(version_str)
            if version < StrictVersion("0.16.1"):
                raise ValueError(
                    f"Geckodriver version {version_str} is too old. 0.16.1 or "
                    f"higher is required. To disable version checking, set "
                    f"`version_check` to `False`."
                )

    async def start(self):
        port = arsenic.utils.free_port()
        await self._check_version()
        return await pyr_subprocess_based_service(
            [self.binary, "--port", str(port)],
            f"http://localhost:{port}",
            self.log_file,
        )


async def pyr_start_session(service, browser, bind=""):
    driver = await service.start()
    return await driver.new_session(browser, bind=bind)


class PyrSessionContext(arsenic.SessionContext):

    async def __aenter__(self):
        self.session = await pyr_start_session(self.service, self.browser,
                                               self.bind)
        return self.session


def pyr_get_session(service, browser, bind=""):
    return PyrSessionContext(service, browser, bind)
