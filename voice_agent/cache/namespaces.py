"""Namespace utilities for hierarchical cache paths."""


def parse_namespace_path(namespace_path: str) -> tuple[str, str]:
    """
    Parse a hierarchical namespace path into namespace and key.
    
    Args:
        namespace_path: Hierarchical path like "apps", "browsers.chrome", "llm.responses"
    
    Returns:
        Tuple of (namespace_path, key) where key is the last segment
        If no dot, returns (namespace_path, "")
    
    Examples:
        parse_namespace_path("apps") -> ("apps", "")
        parse_namespace_path("browsers.chrome") -> ("browsers", "chrome")
        parse_namespace_path("llm.responses") -> ("llm", "responses")
    """
    if "." not in namespace_path:
        return namespace_path, ""
    
    parts = namespace_path.split(".")
    namespace = ".".join(parts[:-1])
    key = parts[-1]
    return namespace, key


def build_namespace_path(*parts: str) -> str:
    """
    Build a hierarchical namespace path from parts.
    
    Args:
        *parts: Path segments
    
    Returns:
        Dot-joined path string
    
    Examples:
        build_namespace_path("browsers", "chrome") -> "browsers.chrome"
        build_namespace_path("apps") -> "apps"
    """
    return ".".join(parts)

