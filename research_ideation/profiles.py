"""兼容入口；Hermes 专有实现位于 runtime.hermes。"""
from .runtime.hermes.profiles import HermesCommand, provision, doctor, schedule, read_yaml, link_plugin
__all__ = ["HermesCommand", "provision", "doctor", "schedule", "read_yaml", "link_plugin"]
