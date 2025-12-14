Detailed Migration Analysis

  Based on my analysis, here's what needs to happen for each services file:

  ---
  1. services/pdf/preprocessing.py (323 lines)

  | Function                   | Lines   | Target Location                     | Reason                              |
  |----------------------------|---------|-------------------------------------|-------------------------------------|
  | COURT_HEADER_PATTERNS      | 18-46   | adapters/pdf/pymupdf.py             | PDF-specific patterns               |
  | is_content_sparse()        | 49-111  | core/extraction/recovery_handler.py | Domain logic (checks entry quality) |
  | strip_court_headers()      | 114-134 | adapters/pdf/pymupdf.py             | PDF preprocessing                   |
  | is_scanned_page()          | 137-187 | adapters/pdf/pymupdf.py             | Already in PDFPort interface        |
  | render_page_to_image()     | 190-203 | adapters/pdf/pymupdf.py             | Already in PDFPort interface        |
  | render_page_to_base64()    | 206-209 | adapters/pdf/pymupdf.py             | Utility                             |
  | get_page_content()         | 212-242 | adapters/pdf/pymupdf.py             | Add to PDFPort                      |
  | get_pages_content()        | 245-279 | adapters/pdf/pymupdf.py             | Add to PDFPort                      |
  | analyze_document_content() | 282-322 | adapters/pdf/pymupdf.py             | Add to PDFPort                      |

  Key insight: is_content_sparse() is domain logic (checks if chronology entry has meaningful content) - should stay in core/, not go to adapter.

  ---
  2. services/pdf/bookmarks/bookmark_extractor.py (376 lines)

  | Class/Method                                | Lines   | Target Location         | Action                          |
  |---------------------------------------------|---------|-------------------------|---------------------------------|
  | Bookmark dataclass                          | 23-45   | core/ports/pdf.py       | ✅ Already exists (but simpler) |
  | BookmarkTree dataclass                      | 48-64   | core/models/            | New model                       |
  | BookmarkExtractor.extract_bookmarks()       | 75-126  | adapters/pdf/pymupdf.py | ✅ Already exists               |
  | BookmarkExtractor.analyze_structure()       | 128-163 | adapters/pdf/pymupdf.py | Add to PDFPort                  |
  | BookmarkExtractor.map_to_content()          | 165-210 | adapters/pdf/pymupdf.py | Add to PDFPort                  |
  | BookmarkExtractor.find_exhibits()           | 212-244 | adapters/pdf/pymupdf.py | Add to PDFPort                  |
  | BookmarkExtractor.find_sections()           | 246-272 | adapters/pdf/pymupdf.py | Add to PDFPort                  |
  | BookmarkExtractor.get_exhibit_page_ranges() | 283-319 | adapters/pdf/pymupdf.py | Add to PDFPort                  |

  ---
  3. services/llm/llm_manager.py (1025 lines)

  | Component            | Lines    | Target Location          | Action                      |
  |----------------------|----------|--------------------------|-----------------------------|
  | LLMProvider enum     | 29-34    | Delete                   | BedrockAdapter is concrete  |
  | LLMConfig dataclass  | 37-82    | core/ports/llm.py        | ✅ Already have ModelConfig |
  | UsageStats dataclass | 85-104   | adapters/llm/bedrock.py  | Add for cost tracking       |
  | RateLimiter class    | 107-129  | adapters/llm/bedrock.py  | Add to adapter              |
  | AnthropicProvider    | 157-261  | Delete                   | Not using direct Anthropic  |
  | ClaudeSDKProvider    | 264-414  | Delete                   | Not using Claude SDK        |
  | BedrockProvider      | 417-656  | adapters/llm/bedrock.py  | ✅ Most already migrated    |
  | LLMManager           | 659-780  | Delete                   | Replaced by port pattern    |
  | CostTracker          | 783-836  | adapters/llm/bedrock.py  | Optional - add if needed    |
  | TokenCounter         | 944-1021 | core/extraction/utils.py | Move if needed              |
  | Factory functions    | 841-942  | Delete                   | DI pattern replaces         |

  Key insight: Most of LLMManager is multi-provider abstraction we don't need. BedrockAdapter should get:
  - UsageStats for tracking
  - RateLimiter for rate limiting
  - Vision method ✅ (already exists in adapter)

  ---
  4. services/generators/ (4 files)

  | File                     | Target                              | Action                      |
  |--------------------------|-------------------------------------|-----------------------------|
  | gotenberg_client.py      | adapters/export/gotenberg.py        | Move + implement ExportPort |
  | html_report_generator.py | adapters/export/html.py             | Move (pure functions)       |
  | markdown_converter.py    | core/builders/markdown_converter.py | Move (uses ExportPort)      |
  | report_exporter.py       | adapters/export/pdf.py              | Move + update imports       |

  ---
  Migration Dependency Order

  1. Expand PDFPort interface (add 6 new methods)
     ↓
  2. Migrate preprocessing.py → PyMuPDFAdapter
     ↓
  3. Migrate BookmarkExtractor → PyMuPDFAdapter
     ↓
  4. Move is_content_sparse → core/extraction/recovery_handler.py
     ↓
  5. Update core/ imports to use PDFPort
     ↓
  6. Create ExportPort + move generators
     ↓
  7. Add RateLimiter/UsageStats to BedrockAdapter
     ↓
  8. Update engine.py to remove LLMManager fallback
     ↓
  9. Move job_processors → workers/
     ↓
  10. Delete services/ directory

  ---
  New PDFPort Methods Required

  # Add to core/ports/pdf.py

  @abstractmethod
  def get_page_content(self, path: str, page: int) -> dict:
      """Get text or image content for single page."""
      pass

  @abstractmethod
  def get_pages_content(self, path: str, start: int, end: int) -> dict:
      """Get content for page range, separating text and images."""
      pass

  @abstractmethod
  def analyze_document(self, path: str, sample_pages: int = 20) -> dict:
      """Analyze document to determine extraction strategy."""
      pass

  @abstractmethod
  def find_exhibits(self, bookmarks: List[Bookmark]) -> List[Bookmark]:
      """Find bookmarks that represent exhibits."""
      pass

  @abstractmethod
  def find_sections(self, bookmarks: List[Bookmark]) -> Dict[str, List[Bookmark]]:
      """Find ERE sections (A, B, D, E, F) from bookmarks."""
      pass

  @abstractmethod
  def get_exhibit_page_ranges(self, path: str) -> List[dict]:
      """Get page ranges for all exhibits in PDF."""
      pass

  @abstractmethod
  def strip_court_headers(self, text: str) -> str:
      """Remove court administrative headers from text."""
      pass

  ---
  Summary

  | Services File         | Lines | Migrated To              | Complexity         |
  |-----------------------|-------|--------------------------|--------------------|
  | preprocessing.py      | 323   | PyMuPDFAdapter + core    | Medium             |
  | bookmark_extractor.py | 376   | PyMuPDFAdapter           | Medium             |
  | llm_manager.py        | 1025  | BedrockAdapter (partial) | Low (most deleted) |
  | generators/*          | ~800  | adapters/export/         | Medium             |
  | dde_parser.py         | ~300  | Keep as domain service   | Low                |

  Total migration work: ~15-20 method implementations across 2 adapters + 1 new port.

  Would you like me to start implementing these migrations? I'd recommend starting with Phase 4.1: Expand PDFPort interface since most other work depends on it.

> We want to keep files under 350 lines if all possible. 

⏺ Good point. Let me revise the migration plan to keep files under 350 lines by splitting into focused modules.

  Revised Structure (All Files < 350 Lines)

  Current Size Analysis

  | File                    | Current Lines | After Migration       | Problem          |
  |-------------------------|---------------|-----------------------|------------------|
  | adapters/pdf/pymupdf.py | 145           | 145 + 323 + 376 = 844 | ❌ Way over      |
  | adapters/llm/bedrock.py | 161           | 161 + ~200 = 361      | ❌ Slightly over |

  Proposed Split Structure

  app/adapters/
  ├── llm/
  │   ├── __init__.py
  │   ├── bedrock.py              # Core LLMPort impl (~200 lines)
  │   ├── rate_limiter.py         # Rate limiting (~60 lines)
  │   └── usage_tracker.py        # Cost/usage tracking (~100 lines)
  │
  ├── pdf/
  │   ├── __init__.py
  │   ├── pymupdf.py              # Core PDFPort impl (~180 lines)
  │   ├── preprocessing.py        # Scanned detection, rendering (~180 lines)
  │   └── bookmarks.py            # Exhibit/section finding (~220 lines)
  │
  ├── storage/
  │   └── redis_adapter.py        # Unchanged (~100 lines)
  │
  └── export/
      ├── __init__.py
      ├── gotenberg.py            # HTTP client for PDF gen (~120 lines)
      ├── html_formatter.py       # HTML generation (~200 lines)
      ├── markdown_converter.py   # MD→PDF conversion (~200 lines)
      └── report_exporter.py      # Orchestrator (~150 lines)

  Core Extraction (Domain Logic Stays in Core)

  app/core/extraction/
  ├── ...existing files...
  ├── content_analyzer.py         # is_content_sparse() - NEW (~80 lines)
  └── court_patterns.py           # COURT_HEADER_PATTERNS - NEW (~50 lines)

  ---
  Revised Migration Plan

⏺ File-by-File Migration Mapping

  From services/pdf/preprocessing.py (323 lines)

  | Component                  | Lines | Target File                         | Est. Lines |
  |----------------------------|-------|-------------------------------------|------------|
  | COURT_HEADER_PATTERNS      | 28    | core/extraction/court_patterns.py   | 50         |
  | is_content_sparse()        | 63    | core/extraction/content_analyzer.py | 80         |
  | strip_court_headers()      | 21    | adapters/pdf/preprocessing.py       | 25         |
  | is_scanned_page()          | 51    | adapters/pdf/preprocessing.py       | 55         |
  | render_page_to_image()     | 14    | adapters/pdf/preprocessing.py       | 15         |
  | render_page_to_base64()    | 4     | adapters/pdf/preprocessing.py       | 5          |
  | get_page_content()         | 31    | adapters/pdf/preprocessing.py       | 35         |
  | get_pages_content()        | 35    | adapters/pdf/preprocessing.py       | 40         |
  | analyze_document_content() | 41    | adapters/pdf/preprocessing.py       | 45         |

  Result: adapters/pdf/preprocessing.py ≈ 180 lines ✅

  ---
  From services/pdf/bookmarks/bookmark_extractor.py (376 lines)

  | Component                 | Lines | Target File                     | Est. Lines |
  |---------------------------|-------|---------------------------------|------------|
  | Bookmark dataclass        | 23    | Keep in core/ports/pdf.py       | 0 (exists) |
  | BookmarkTree dataclass    | 17    | core/models/bookmark.py         | 25         |
  | extract_bookmarks()       | 52    | Keep in adapters/pdf/pymupdf.py | 0 (exists) |
  | analyze_structure()       | 36    | adapters/pdf/bookmarks.py       | 40         |
  | map_to_content()          | 46    | adapters/pdf/bookmarks.py       | 50         |
  | find_exhibits()           | 33    | adapters/pdf/bookmarks.py       | 35         |
  | find_sections()           | 27    | adapters/pdf/bookmarks.py       | 30         |
  | export_to_json()          | 8     | adapters/pdf/bookmarks.py       | 10         |
  | get_exhibit_page_ranges() | 37    | adapters/pdf/bookmarks.py       | 40         |
  | main() CLI                | 50    | Delete                          | 0          |

  Result: adapters/pdf/bookmarks.py ≈ 220 lines ✅

  ---
  From services/llm/llm_manager.py (1025 lines)

  | Component            | Lines | Target                        | Action                  |
  |----------------------|-------|-------------------------------|-------------------------|
  | LLMProvider enum     | 6     | Delete                        | Not needed              |
  | LLMConfig dataclass  | 45    | Delete                        | Use ModelConfig in port |
  | UsageStats dataclass | 20    | adapters/llm/usage_tracker.py | Keep                    |
  | RateLimiter class    | 23    | adapters/llm/rate_limiter.py  | Keep                    |
  | BaseLLMProvider ABC  | 25    | Delete                        | Use port                |
  | AnthropicProvider    | 105   | Delete                        | Not using               |
  | ClaudeSDKProvider    | 151   | Delete                        | Not using               |
  | BedrockProvider      | 240   | Already in bedrock.py         | Partial                 |
  | LLMManager           | 122   | Delete                        | Port pattern            |
  | CostTracker          | 54    | adapters/llm/usage_tracker.py | Keep                    |
  | Factory functions    | 102   | Delete                        | DI pattern              |
  | TokenCounter         | 78    | core/extraction/utils.py      | Optional                |

  Result:
  - adapters/llm/rate_limiter.py ≈ 60 lines ✅
  - adapters/llm/usage_tracker.py ≈ 100 lines ✅
  - adapters/llm/bedrock.py stays ≈ 200 lines ✅

  ---
  From services/generators/ (~800 lines total)

  | File                     | Lines | Target                       | Est. Lines |
  |--------------------------|-------|------------------------------|------------|
  | gotenberg_client.py      | ~150  | adapters/export/gotenberg.py | 120        |
  | html_report_generator.py | ~250  | adapters/export/html.py      | 200        |
  | markdown_converter.py    | ~250  | adapters/export/markdown.py  | 200        |
  | report_exporter.py       | ~150  | adapters/export/pdf.py       | 150        |

  All under 350 ✅

  ---
  Summary: New File Structure

  | New File                            | Lines | Content                          |
  |-------------------------------------|-------|----------------------------------|
  | core/extraction/content_analyzer.py | ~80   | is_content_sparse() domain logic |
  | core/extraction/court_patterns.py   | ~50   | COURT_HEADER_PATTERNS            |
  | core/models/bookmark.py             | ~25   | BookmarkTree dataclass           |
  | adapters/pdf/preprocessing.py       | ~180  | Scanned detection, rendering     |
  | adapters/pdf/bookmarks.py           | ~220  | Exhibit/section finding          |
  | adapters/llm/rate_limiter.py        | ~60   | Rate limiting                    |
  | adapters/llm/usage_tracker.py       | ~100  | Cost tracking                    |
  | adapters/export/gotenberg.py        | ~120  | PDF generation client            |
  | adapters/export/html.py             | ~200  | HTML formatting                  |
  | adapters/export/markdown.py         | ~200  | MD→PDF conversion                |
  | adapters/export/pdf.py              | ~150  | Export orchestration             |

  All files under 350 lines ✅

  ---
  Would you like me to start implementing? I recommend beginning with:
  1. core/extraction/content_analyzer.py - Moves domain logic out of services
  2. adapters/pdf/preprocessing.py - Enables removing services/pdf/preprocessing.py import

> What is a good rule of thumb for best modularization practices and clean architecute 

⏺ Great question. Here are the key principles:

  Clean Architecture Rules of Thumb

  1. Single Responsibility = One Reason to Change

  ❌ UserService: handles auth, profiles, notifications, billing
  ✅ AuthService, ProfileService, NotificationService, BillingService

  Test: "If X changes, does this file need to change?" If multiple X's → split.

  ---
  2. Dependency Rule: Inward Only

  Adapters → Core → Ports
     ↓         ↓       ↓
  External   Domain   Interfaces

  - Core never imports from adapters or infrastructure
  - Adapters implement port interfaces
  - Dependencies point toward the center (domain)

  ---
  3. Cohesion Over Coupling

  | High Cohesion ✅                             | Low Cohesion ❌                       |
  |----------------------------------------------|---------------------------------------|
  | Functions that change together live together | Utils grab-bag with unrelated helpers |
  | pdf/bookmarks.py - all bookmark logic        | helpers.py with 50 random functions   |

  Rule: If you often edit files A and B together, they should probably be one file (or same module).

  ---
  4. File Size Guidelines

  | Lines   | Assessment                            |
  |---------|---------------------------------------|
  | < 100   | Maybe too granular (consider merging) |
  | 100-300 | Sweet spot ✅                         |
  | 300-500 | Getting large, look for split points  |
  | > 500   | Almost always needs splitting         |

  Split signals:
  - Multiple classes with different responsibilities
  - Scrolling to find things
  - Large import blocks
  - Multiple unrelated test files

  ---
  5. Module Naming = Intent

  ❌ utils.py, helpers.py, misc.py, common.py
  ✅ rate_limiter.py, content_analyzer.py, court_patterns.py

  Test: Can someone guess what's in the file from the name?

  ---
  6. The 7±2 Rule

  A module should have 5-9 public functions/classes. More than that → split.

  # ❌ Too many responsibilities
  class PDFAdapter:
      extract_text()
      extract_bookmarks()
      find_exhibits()
      find_sections()
      is_scanned()
      render_image()
      strip_headers()
      get_content()
      analyze_document()
      export_json()
      get_page_ranges()
      # ... 15 more methods

  # ✅ Composed from focused modules
  class PDFAdapter:
      def __init__(self):
          self.preprocessor = Preprocessor()
          self.bookmark_analyzer = BookmarkAnalyzer()

      extract_text()        # Core
      extract_bookmarks()   # Core
      render_page()         # Core
      # Delegate specialized work to composed modules

  ---
  7. Domain Logic vs Infrastructure

  | Domain (core/)                       | Infrastructure (adapters/)               |
  |--------------------------------------|------------------------------------------|
  | is_content_sparse() - business rule  | is_scanned_page() - PDF detection        |
  | VALID_VISIT_TYPES - domain constants | COURT_HEADER_PATTERNS - parsing patterns |
  | Entry validation                     | HTTP clients                             |
  | Business calculations                | File I/O                                 |

  Test: "Would this exist if we changed our PDF library?"
  - No → Domain
  - Yes → Infrastructure

  ---
  8. Interface Segregation

  # ❌ Fat interface - forces implementers to stub unused methods
  class PDFPort(ABC):
      extract_text()
      extract_bookmarks()
      find_exhibits()
      render_image()
      send_email()  # Why is this here?

  # ✅ Focused interfaces
  class TextExtractorPort(ABC):
      extract_text()

  class BookmarkExtractorPort(ABC):
      extract_bookmarks()
      find_exhibits()

  Rule: Clients shouldn't depend on methods they don't use.

  ---
  9. Testing Tells You

  | Symptom                                 | Problem               | Solution          |
  |-----------------------------------------|-----------------------|-------------------|
  | Tests need 10+ mocks                    | Too many dependencies | Split or inject   |
  | Tests break when unrelated code changes | High coupling         | Extract interface |
  | Hard to test one function               | Functions do too much | Split function    |
  | Test file > 500 lines                   | Module too complex    | Split module      |

  ---
  Quick Decision Framework

  When adding new code, ask:

  1. Does this belong with existing code? (cohesion)
     → Same reason to change? Same file.

  2. Is this domain or infrastructure?
     → Business rule? core/
     → External system? adapters/

  3. Will this file exceed 300 lines?
     → Look for natural split points

  4. Can I name it specifically?
     → If only "utils" fits, reconsider structure

  ---
  Applied to Your Migration

  | Current Problem                       | Principle Violated | Fix                        |
  |---------------------------------------|--------------------|----------------------------|
  | core/ imports from services/          | Dependency rule    | Use ports                  |
  | llm_manager.py = 1025 lines           | File size, SRP     | Split by responsibility    |
  | preprocessing.py mixes domain + infra | Domain separation  | is_content_sparse → core   |
  | BookmarkExtractor does everything     | SRP, 7±2 rule      | Split into focused modules |

  Want me to start implementing with these principles in mind?