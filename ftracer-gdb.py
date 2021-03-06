# dump ftracer from multiple threads interleaved from gdb
# load in gdb with "source ftracer-gdb.py" and run as "ftracer"
#
# Copyright (c) 2013 Intel Corporation
# Author: Andi Kleen
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that: (1) source code distributions
# retain the above copyright notice and this paragraph in its entirety, (2)
# distributions including binary code include the above copyright notice and
# this paragraph in its entirety in the documentation or other materials
# provided with the distribution
#
# THIS SOFTWARE IS PROVIDED ``AS IS'' AND WITHOUT ANY EXPRESS OR IMPLIED
# WARRANTIES, INCLUDING, WITHOUT LIMITATION, THE IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE.
import gdb
import re
import collections

# field lengths. can be tweaked, especially if you have very long
# identifiers or long delays
THR_WIDTH = 25
TSTAMP_WIDTH = 8

def getstr(v):
    v = "%s" % (v,)
    t = re.search('"(.+)"', v)
    if t:
        return t.group(1)
    return v

def resolve_with_off(v):
    x = gdb.execute("p/a %d" % (v,), False, True)
    m = re.search(r'<(.*)>', x)
    return m.group(1)

def resolve(v):
    v = resolve_with_off(v)
    m = re.match(r'(.*)\+.*', v)
    return m.group(1)

class Thr:
    def __init__(self):
        self.stack = []

    def update(self, rsp):
        if rsp == 0 or not self.stack or rsp < self.stack[-1]:
            self.stack.append(rsp)
        else:
            while self.stack and rsp > self.stack[-1]:
                self.stack.pop()

    def level(self):
        return len(self.stack) - 1

class Ftracer (gdb.Command): 
    def __init__(self):
        super (Ftracer, self).__init__("ftracer", gdb.COMMAND_NONE, gdb.COMPLETE_SYMBOL)

    def invoke(self, arg, from_tty):
        args = arg.split()
        max = 0
        if len(args) >= 1:
            max = int(args[0])
        events = collections.defaultdict(list)
        frequency = float(gdb.selected_frame().read_var("ftracer_frequency"))
        thr_max = 0
        for i in gdb.inferiors():
            for t in i.threads():
                gdb.execute("thread %d" % (t.num,))
                ftracer_len = gdb.selected_frame().read_var("ftracer_size") 
                x = gdb.selected_frame().read_var("ftracer_tbuf")
                for j in range(0, ftracer_len-1):
                    v = x[j]
                    tstamp = int(v["tstamp"])
                    if tstamp:
                        o = (t.num, v["func"], v["arg1"], v["arg2"], v["arg3"], v["rsp"])
                        events[tstamp].append(o)
                        if int(t.num) > thr_max:
                            thr_max = int(t.num)
        print ("%*s %*s %3s %-*s %s" %
                (TSTAMP_WIDTH, "TIME",
                 TSTAMP_WIDTH, "DELTA", "THR",
                 THR_WIDTH * thr_max, "FUNC", "ARGS"))
        prev = 0
        delta = 0
        start = 0
        threads = collections.defaultdict(Thr)
        k = sorted(events.keys())
        if max:
            k = collections.deque(k, max)
        for t in k:
            if prev:
                delta = t - prev
            if start == 0:
                start = t
            for e in events[t]:
                tnum = e[0]
                thr = threads[tnum]
                thr.update(int(e[5]))
		if thr_max >= 8:
			func = "<%d> " % (tnum)
			width = 30
		else:
                	func = " " * (THR_WIDTH * (tnum-1)) 
                       	width = THR_WIDTH * thr_max,
                func += " " * (thr.level() * 2) 
                func += resolve(int(e[1]))
                print "%*.2f %*.2f %3d %-*s %x %x %x" % (
                       TSTAMP_WIDTH,
                       (t - start) / frequency,
                       TSTAMP_WIDTH,
                       delta / frequency,
                       tnum,
		       width,
                       func,
                       int(e[2]), int(e[3]), int(e[4]))
            prev = t

Ftracer()
