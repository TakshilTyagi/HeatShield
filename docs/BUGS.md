# Known Issues and Bug Tracker

This document records all defects, reproduction steps, severities, and verified resolutions discovered during automated and manual QA cycles across PASS 1 and PASS 2.

| Bug ID | Title & Description | Component | Severity | Reproduction Steps | Resolution / Verification |
|--------|---------------------|-----------|----------|--------------------|---------------------------|
| BUG-01 | Missing SQL query binding parameter in `auto_assign_visits_internal` | `routes/admin.py` | High | Run `auto_assign_visits_internal` with `today_str`. SQLite raised `ProgrammingError: Incorrect number of bindings supplied`. | Fixed by passing `(today_str,)` tuple into `cursor.execute()`. Verified with `tests/test_assignment.py` passing. |
| BUG-02 | Unauthenticated redirect test failure due to shared test client session | `tests/test_smoke.py` | Medium | In `test_smoke.py`, previous tests populated session cookies, causing redirect to user's dashboard rather than `/login`. | Fixed by instantiating `self.app.test_client()` in `test_role_based_access_redirect` to enforce pure unauthenticated state. |
| BUG-03 | Auto-assignment test failing due to persistent assignments from previous test run | `tests/test_assignment.py` | Medium | When running tests sequentially against seeded DB, today's assignments already existed, resulting in 0 new assignments. | Added explicit `DELETE FROM assignments WHERE assigned_date = ?` in the test setup. Verified 100% pass. |
| BUG-04 | SQLite Date Adapter deprecation warnings on Python 3.12+ | `database.py` | Low | Initializing DB raised `DeprecationWarning: The default date adapter is deprecated as of Python 3.12`. | Explicitly cast `past_d` and `today` instances to `str(d)` before passing as SQL parameter bindings. |
| BUG-05 | Hard-coded city name and ward references across templates | `templates/` | High | Changing city or registering from another city displayed "Bareilly" in resident cooling and admin map. | Replaced static strings with dynamic `city.name` and coordinates from user session / database. |
| BUG-06 | Auto-assign was not city-scoped, mixing volunteers across cities | `routes/admin.py` | Critical | When Jaipur admin ran auto-assign, volunteers from Bareilly were eligible candidates. | Filtered households and volunteers by `city_id = ?` in `auto_assign_visits_internal`. Added isolation test `test_cross_city_data_isolation` in `test_locations.py`. |
| BUG-07 | Register form failed to populate cities dynamically | `templates/register.html` | Medium | Register page required State > City cascade, but initially only supported static ward select. | Implemented `/api/locations/cities` and `/api/locations/wards` endpoints and dynamic JavaScript dropdown cascade. |

**Current Open Bugs:** 0  
**Automated Tests:** 18/18 passing (`OK`).  
**Status:** Verified clean and ready for deployment.
