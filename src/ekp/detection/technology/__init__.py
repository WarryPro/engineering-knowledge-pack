"""Technology stack detectors."""

from ekp.detection.technology.base import TechnologyDetector
from ekp.detection.technology.devops import DevOpsDetector
from ekp.detection.technology.flutter import FlutterDetector
from ekp.detection.technology.frontend import FrontendDetector
from ekp.detection.technology.nativescript import NativeScriptDetector
from ekp.detection.technology.php import PHPDetector
from ekp.detection.technology.symfony import SymfonyDetector
from ekp.detection.technology.typescript import TypeScriptDetector

DEFAULT_DETECTORS = (
    SymfonyDetector(),
    PHPDetector(),
    TypeScriptDetector(),
    FrontendDetector(),
    NativeScriptDetector(),
    FlutterDetector(),
    DevOpsDetector(),
)

__all__ = ["TechnologyDetector", "DEFAULT_DETECTORS"]
