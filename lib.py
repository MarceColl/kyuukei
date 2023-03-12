from types import CodeType
from bytecode import Instr, Bytecode, Label
import dis
from math import sqrt

breakpoints = {}

traces = []

def __breakpoint(loc, bid, lineno):
    breakpoints[bid](loc, lineno)

def test_function():
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


def send_trace(lineno, variables):
    trace = { "line": lineno, "vars": variables }
    print(f"Sent trace {trace}")
    traces.append(trace)


def set_breakpoint(module, func_name, line):
    module = __import__(module)
    func = getattr(module, func_name)
    var_names = func.__code__.co_varnames
    code = Bytecode.from_code(func.__code__)

    breakpoint_id = 'asdfasdf'
    def breakpoint_impl(loc, lineno):
        send_trace(lineno, { name: loc.get(name) for name in var_names })

    breakpoints[breakpoint_id] = breakpoint_impl

    new_code = []
    inserted = False

    for instr in code:
        if not isinstance(instr, Label) and instr.lineno == line and not inserted:
            inserted = True

            if instr.name == 'LOAD_GLOBAL' and instr.arg == '__breakpoint':
                pass
            else:
                new_code.append(Instr('LOAD_GLOBAL', '__breakpoint', lineno=line))
                new_code.append(Instr('LOAD_GLOBAL', 'locals', lineno=line))
                new_code.append(Instr('CALL_FUNCTION', 0, lineno=line))
                new_code.append(Instr('LOAD_CONST', breakpoint_id, lineno=line))
                new_code.append(Instr('LOAD_CONST', line, lineno=line))
                new_code.append(Instr('CALL_FUNCTION', 3, lineno=line))
                new_code.append(Instr('POP_TOP', lineno=line))

        new_code.append(instr)

    new_bc = Bytecode(new_code)
    new_bc.argnames = code.argnames
    func.__code__ = new_bc.to_code()
    dis.dis(func)


def trace_func(module, func_name):
    module = __import__(module)
    func = getattr(module, func_name)
    var_names = func.__code__.co_varnames
    code = Bytecode.from_code(func.__code__)

    breakpoint_id = 'asdfasdf'
    def breakpoint_impl(loc, lineno):
        send_trace(lineno, { name: loc.get(name) for name in var_names })

    breakpoints[breakpoint_id] = breakpoint_impl

    new_code = []

    prev_line = -1
    for instr in code:
        if not isinstance(instr, Label) and instr.lineno != prev_line:
            line = instr.lineno
            prev_line = instr.lineno

            new_code.append(Instr('LOAD_GLOBAL', '__breakpoint', lineno=line))
            new_code.append(Instr('LOAD_GLOBAL', 'locals', lineno=line))
            new_code.append(Instr('CALL_FUNCTION', 0, lineno=line))
            new_code.append(Instr('LOAD_CONST', breakpoint_id, lineno=line))
            new_code.append(Instr('LOAD_CONST', line, lineno=line))
            new_code.append(Instr('CALL_FUNCTION', 3, lineno=line))
            new_code.append(Instr('POP_TOP', lineno=line))

        new_code.append(instr)

    new_bc = Bytecode(new_code)
    new_bc.argnames = code.argnames
    func.__code__ = new_bc.to_code()


def print_traces():
    signals = []

    for var in traces[0]["vars"].keys():
        signal = {"name": var, "wave": "z", "data": ""}
        initial_value = None
        counter = 2
        for trace in traces:
            if trace["vars"][var] != initial_value:
                signal["wave"] = f"{signal['wave']}{counter}"
                signal["data"] = f"{signal['data']}{trace['vars'][var]} "
                initial_value = trace['vars'][var]
                counter += 1
            else:
                signal["wave"] = f"{signal['wave']}."

        print(signal)

        signals.append(signal)

    import json
    import wavedrom
    wavedrom.render(json.dumps({"signal": signals, "head": { "tock": 0 }})).saveas("demo1.svg")


def init():
    globals()["__breakpoint"] = __breakpoint


init()
