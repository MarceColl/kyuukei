import uuid
import asyncio
import builtins
import dis
import os
from math import sqrt
from types import CodeType

import simdjson
import aiohttp
from aiohttp import web
from bytecode import Bytecode, Instr, Label

import otherlib

breakpoints = {}

traces = []

KK_EXPOSE_BIND = os.getenv("KK_EXPOSE_BIND", "0.0.0.0")
KK_EXPOSE_PORT = int(os.getenv("KK_EXPOSE_PORT", "8855"))

KK_SERVER_HOST = os.getenv("KK_SERVER_HOST", "http://localhost:8854")


tasks = set()


def __breakpoint(loc, bid, lineno):
    breakpoints[bid](loc, lineno)


def test_function():
    print("TEST")
    a = 12
    b = 14
    c = a * b
    d = b - a
    e = a * b - c * d

    for i in range(4):
        c = d * b - e
        d = c - a + e
        e = sqrt(c + d)

    return c / d


def patch_func(func, co_code):
    func.__code__ = func.__code__.replace(co_code=co_code)


async def send_trace_task(trace):
    try:
        async with aiohttp.ClientSession(json_serialize=simdjson.dumps) as session: 
            await session.post(f"{KK_SERVER_HOST}/trace", json=trace)
    except aiohttp.ClientError as e:
        print(f"kyuukei error: {e}")


def send_trace(lineno, variables):
    trace = {"line": lineno, "vars": variables}
    task = asyncio.create_task(send_trace_task(trace))
    tasks.add(task)
    task.add_done_callback(tasks.discard)


def set_breakpoint(module, func_name, line):
    module = __import__(module)
    func = getattr(module, func_name)
    var_names = func.__code__.co_varnames
    code = Bytecode.from_code(func.__code__)

    breakpoint_id = uuid.uuid4().hex

    def breakpoint_impl(loc, lineno):
        send_trace(lineno, {name: loc.get(name) for name in var_names})

    breakpoints[breakpoint_id] = breakpoint_impl

    new_code = []
    inserted = False

    for instr in code:
        if not isinstance(instr, Label) and instr.lineno == line and not inserted:
            inserted = True

            if instr.name == "LOAD_GLOBAL" and instr.arg == "__breakpoint":
                pass
            else:
                new_code.append(Instr("LOAD_GLOBAL", "__breakpoint", lineno=line))
                new_code.append(Instr("LOAD_GLOBAL", "locals", lineno=line))
                new_code.append(Instr("CALL_FUNCTION", 0, lineno=line))
                new_code.append(Instr("LOAD_CONST", breakpoint_id, lineno=line))
                new_code.append(Instr("LOAD_CONST", line, lineno=line))
                new_code.append(Instr("CALL_FUNCTION", 3, lineno=line))
                new_code.append(Instr("POP_TOP", lineno=line))

        new_code.append(instr)

    new_bc = Bytecode(new_code)
    new_bc.argnames = code.argnames
    func.__code__ = new_bc.to_code()
    dis.dis(func)


def trace_func(module, func_name):
    print(f"TRACING {module}:{func_name}")
    module = __import__(module)
    func = getattr(module, func_name)
    var_names = func.__code__.co_varnames
    code = Bytecode.from_code(func.__code__)

    breakpoint_id = uuid.uuid4().hex

    def breakpoint_impl(loc, lineno):
        send_trace(lineno, {name: loc.get(name) for name in var_names})

    breakpoints[breakpoint_id] = breakpoint_impl

    new_code = []

    prev_line = -1
    for instr in code:
        if not isinstance(instr, Label) and instr.lineno != prev_line:
            line = instr.lineno
            prev_line = instr.lineno

            new_code.append(Instr("LOAD_GLOBAL", "__breakpoint", lineno=line))
            new_code.append(Instr("LOAD_GLOBAL", "locals", lineno=line))
            new_code.append(Instr("CALL_FUNCTION", 0, lineno=line))
            new_code.append(Instr("LOAD_CONST", breakpoint_id, lineno=line))
            new_code.append(Instr("LOAD_CONST", line, lineno=line))
            new_code.append(Instr("CALL_FUNCTION", 3, lineno=line))
            new_code.append(Instr("POP_TOP", lineno=line))

        new_code.append(instr)

    new_bc = Bytecode(new_code)
    new_bc.argnames = code.argnames
    func.__code__ = new_bc.to_code()

    return breakpoint_id


async def trace_handler(request):
    req = await request.json(loads=simdjson.loads)
    trace_func(req["module"], req["function"])
    return web.Response(text="DONE")


async def test_handler(request):
    return web.Response(text=str(otherlib.test_function()))


async def init():
    setattr(builtins, "__breakpoint", __breakpoint)

    app = web.Application()
    app.add_routes(
        [
            web.post("/trace", trace_handler),
            web.get("/test", test_handler),
        ]
    )
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, KK_EXPOSE_BIND, KK_EXPOSE_PORT)
    print(f"==== Started kyuukei listener at http://{KK_EXPOSE_BIND}:{KK_EXPOSE_PORT} ====")
    await site.start()

    while True:
        await asyncio.sleep(3600)


def main():
    asyncio.run(init())


if __name__ == "__main__":
    main()
