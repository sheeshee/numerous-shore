# broker.py A message broker for MicroPython

# Copyright (c) 2024-2025 Peter Hinch
# Released under the MIT License (MIT) - see LICENSE file

# Inspired by the following
# https://www.joeltok.com/posts/2021-03-building-an-event-bus-in-python/

import asyncio
from primitives import Queue, RingbufQueue, type_coro
import re


class Agent:  # ABC for user agent
    pass


class RegExp:
    def __init__(self, re_str):
        self.re = re.compile(re_str)

    def matching(self, topic):
        return re.match(self.re, topic) is not None


def _validate(a):
    return (
        isinstance(a, asyncio.Event)
        or isinstance(a, Queue)
        or isinstance(a, RingbufQueue)
        or isinstance(a, Agent)
        or callable(a)
    )


class Broker(dict):
    Verbose = True

    def subscribe(self, topic, agent, *args):
        if not _validate(agent):
            raise ValueError("Invalid agent:", agent)
        aa = (agent, args)
        if not (t := self.get(topic, False)):
            self[topic] = {aa}
        else:
            if aa in t and Broker.Verbose:
                print(f"Duplicate agent {aa} in topic {topic}.")
            t.add(aa)

    def unsubscribe(self, topic, agent, *args):
        if topic in self:
            if (aa := (agent, args)) in self[topic]:
                self[topic].remove(aa)
            elif Broker.Verbose:
                print(f"Unsubscribe agent {aa} from topic {topic} fail: agent not subscribed.")
            if len(self[topic]) == 0:
                del self[topic]
        elif Broker.Verbose:
            print(f"Unsubscribe topic {topic} fail: topic not subscribed.")

    def publish(self, topic, message=None):
        agents = set()  # Agents which are triggered by this topic
        if isinstance(topic, str):  # Check regexps
            # Are any keys RegExp instances?
            for regexp in [k for k in self.keys() if isinstance(k, RegExp)]:
                if regexp.matching(topic):
                    agents.update(self[regexp])  # Append matching agents
        agents.update(self.get(topic, []))  # Exact match
        for agent, args in agents:
            if isinstance(agent, asyncio.Event):
                agent.set()
                continue
            if isinstance(agent, Agent):  # User class
                agent.put(topic, message, *args)  # Must support .put
                continue
            if isinstance(agent, Queue) or isinstance(agent, RingbufQueue):
                t = (topic, message, args)
                try:
                    agent.put_nowait(t if args else t[:2])
                except Exception:  # Queue discards current message. RingbufQueue discards oldest
                    Broker.Verbose and print(f"Message lost topic {topic} message {message}")
                continue
            # agent is function, method, coroutine or bound coroutine
            res = agent(topic, message, *args)
            if isinstance(res, type_coro):
                asyncio.create_task(res)


broker = Broker()
