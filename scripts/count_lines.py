#!/usr/bin/env python3
"""
程式碼行數統計腳本

統計專案中各類型檔案的程式碼行數，包含：
- 總行數
- 空白行數
- 註解行數
- 實際程式碼行數

Usage:
    python scripts/count_lines.py
"""

import os
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class FileStats:
    """單一檔案的統計資料"""
    total_lines: int = 0
    blank_lines: int = 0
    comment_lines: int = 0
    code_lines: int = 0


@dataclass
class ExtensionStats:
    """按副檔名分類的統計資料"""
    file_count: int = 0
    total_lines: int = 0
    blank_lines: int = 0
    comment_lines: int = 0
    code_lines: int = 0


# 要排除的目錄
EXCLUDE_DIRS = {
    "__pycache__",
    ".git",
    ".venv",
    "venv",
    "env",
    "node_modules",
    ".idea",
    ".vscode",
    "logs",
    ".pytest_cache",
    ".mypy_cache",
    "htmlcov",
    "dist",
    "build",
    "*.egg-info",
}

# 要統計的副檔名
CODE_EXTENSIONS = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".html": "HTML",
    ".css": "CSS",
    ".json": "JSON",
    ".yml": "YAML",
    ".yaml": "YAML",
    ".md": "Markdown",
    ".sql": "SQL",
    ".sh": "Shell",
    ".ps1": "PowerShell",
    ".toml": "TOML",
    ".ini": "INI",
    ".env": "Environment",
    ".txt": "Text",
}

# 各語言的註解符號
COMMENT_MARKERS = {
    ".py": ("#", '"""', "'''"),
    ".js": ("//", "/*"),
    ".ts": ("//", "/*"),
    ".html": ("<!--",),
    ".css": ("/*",),
    ".sh": ("#",),
    ".ps1": ("#",),
    ".yml": ("#",),
    ".yaml": ("#",),
    ".toml": ("#",),
    ".ini": ("#", ";"),
    ".sql": ("--", "/*"),
}


def is_comment_line(line: str, ext: str) -> bool:
    """檢查是否為註解行"""
    stripped = line.strip()
    if not stripped:
        return False
    
    markers = COMMENT_MARKERS.get(ext, ())
    for marker in markers:
        if stripped.startswith(marker):
            return True
    return False


def count_file_lines(file_path: Path) -> FileStats:
    """統計單一檔案的行數"""
    stats = FileStats()
    ext = file_path.suffix.lower()
    
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                stats.total_lines += 1
                
                if not line.strip():
                    stats.blank_lines += 1
                elif is_comment_line(line, ext):
                    stats.comment_lines += 1
                else:
                    stats.code_lines += 1
    except Exception as e:
        print(f"  ⚠️ 無法讀取: {file_path} ({e})")
    
    return stats


def should_exclude(path: Path) -> bool:
    """檢查是否應該排除此路徑"""
    for part in path.parts:
        if part in EXCLUDE_DIRS:
            return True
    return False


def count_project_lines(root_dir: Path) -> dict[str, ExtensionStats]:
    """統計整個專案的行數"""
    stats_by_ext: dict[str, ExtensionStats] = defaultdict(ExtensionStats)
    
    for file_path in root_dir.rglob("*"):
        # 跳過目錄
        if file_path.is_dir():
            continue
        
        # 跳過排除的目錄
        if should_exclude(file_path):
            continue
        
        ext = file_path.suffix.lower()
        
        # 只統計已知的程式碼檔案類型
        if ext not in CODE_EXTENSIONS:
            continue
        
        file_stats = count_file_lines(file_path)
        
        stats_by_ext[ext].file_count += 1
        stats_by_ext[ext].total_lines += file_stats.total_lines
        stats_by_ext[ext].blank_lines += file_stats.blank_lines
        stats_by_ext[ext].comment_lines += file_stats.comment_lines
        stats_by_ext[ext].code_lines += file_stats.code_lines
    
    return dict(stats_by_ext)


def print_report(stats: dict[str, ExtensionStats]) -> None:
    """輸出統計報告"""
    print("\n" + "=" * 80)
    print("📊 程式碼行數統計報告")
    print("=" * 80)
    
    # 表頭
    print(f"\n{'語言':<12} {'檔案數':>8} {'總行數':>10} {'程式碼':>10} {'註解':>8} {'空白':>8}")
    print("-" * 60)
    
    # 各語言統計
    total_files = 0
    total_lines = 0
    total_code = 0
    total_comments = 0
    total_blank = 0
    
    sorted_stats = sorted(
        stats.items(),
        key=lambda x: x[1].code_lines,
        reverse=True
    )
    
    for ext, ext_stats in sorted_stats:
        lang_name = CODE_EXTENSIONS.get(ext, ext)
        print(
            f"{lang_name:<12} "
            f"{ext_stats.file_count:>8} "
            f"{ext_stats.total_lines:>10,} "
            f"{ext_stats.code_lines:>10,} "
            f"{ext_stats.comment_lines:>8,} "
            f"{ext_stats.blank_lines:>8,}"
        )
        
        total_files += ext_stats.file_count
        total_lines += ext_stats.total_lines
        total_code += ext_stats.code_lines
        total_comments += ext_stats.comment_lines
        total_blank += ext_stats.blank_lines
    
    # 總計
    print("-" * 60)
    print(
        f"{'總計':<12} "
        f"{total_files:>8} "
        f"{total_lines:>10,} "
        f"{total_code:>10,} "
        f"{total_comments:>8,} "
        f"{total_blank:>8,}"
    )
    
    # 百分比統計
    if total_lines > 0:
        print("\n📈 比例分析:")
        print(f"   程式碼: {total_code / total_lines * 100:.1f}%")
        print(f"   註解:   {total_comments / total_lines * 100:.1f}%")
        print(f"   空白:   {total_blank / total_lines * 100:.1f}%")
    
    print("\n" + "=" * 80)


def main():
    """主程式"""
    # 取得專案根目錄
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    print(f"🔍 掃描目錄: {project_root}")
    
    stats = count_project_lines(project_root)
    
    if not stats:
        print("❌ 找不到任何程式碼檔案")
        return
    
    print_report(stats)


if __name__ == "__main__":
    main()
