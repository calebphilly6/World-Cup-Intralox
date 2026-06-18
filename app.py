from __future__ import annotations

import base64
import hmac
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import streamlit as st
import streamlit.components.v1 as components

from src.config import ensure_app_directories, get_app_config, get_secret, is_shared_core_read_only_mode
from src.database import fetch_df, initialize_database
from src.football_data_service import clear_football_data_cache
from src.pages import bracket, dashboard, fixtures, groups, history, rankings, teams, wcq, work_competition
from src.pages import odds
from src.reference_data import seed_world_cup_2026_reference_data
from src.snapshots import core_snapshots_available, load_core_snapshots
from src.storage.browser_preferences import clear_browser_preferences, render_browser_preferences_bridge
from src.storage.storage import preferences_are_session_only
from src.match_odds_service import refresh_match_odds_if_available
from src.navigation import clear_detail_origins
from src.odds_refresh import daily_odds_refresh_key
from src.odds_service import latest_tournament_winner_odds
from src.tournament_odds_service import refresh_tournament_odds_if_available


PROJECT_ROOT = Path(__file__).resolve().parent
LOGO_PATH = PROJECT_ROOT / "assets" / "world_cup_2026_logo.png"


st.set_page_config(
    page_title="World Cup 2026 Command Center",
    layout="wide",
    initial_sidebar_state="collapsed",
)


NAV_PAGES = {
    "Home": dashboard.render,
    "Fixtures": fixtures.render,
    "Groups": groups.render,
    "Bracket": bracket.render,
    "Work Competition": work_competition.render,
    "Teams": teams.render,
    "Odds": odds.render,
    "FIFA Rankings": rankings.render,
    "WCQ": wcq.render,
    "History": history.render,
}

PAGES = NAV_PAGES

PAGE_SLUGS = {
    "Home": "home",
    "Teams": "teams",
    "Fixtures": "fixtures",
    "Groups": "groups",
    "History": "history",
    "WCQ": "wcq",
    "Bracket": "bracket",
    "FIFA Rankings": "fifa-rankings",
    "Odds": "odds",
    "Work Competition": "work-competition",
}

SLUG_TO_PAGE = {slug: page_name for page_name, slug in PAGE_SLUGS.items()}

NAV_LABELS = {
    "Work Competition": "Intralox",
}

PAGE_ALIASES = {
    "Home Dashboard": "Home",
    "Knockout Round": "Bracket",
}


def _image_data_uri(path: Path) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _logo_data_uri() -> str | None:
    if not LOGO_PATH.exists():
        return None
    return _image_data_uri(LOGO_PATH)


def _apply_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
            --wc-black: #050505;
            --wc-charcoal: #111111;
            --wc-navy: #0B1020;
            --wc-white: #FFFFFF;
            --wc-gold: #D6A83A;
            --wc-deep-gold: #9E7420;
            --wc-blue: #2458FF;
            --wc-cyan: #23D7D7;
            --wc-lime: #9DFF00;
            --wc-red-orange: #FF3B1F;
            --wc-purple: #6A00FF;
        }

        .stApp {
            background:
                radial-gradient(circle at 18% 8%, rgba(36, 88, 255, .24), transparent 30%),
                radial-gradient(circle at 84% 14%, rgba(214, 168, 58, .24), transparent 30%),
                linear-gradient(135deg, #141827 0%, #18213A 48%, #1B1B1B 100%);
            color: var(--wc-white);
        }

        [data-testid="stHeader"] {
            background: transparent;
        }

        [data-testid="stSidebar"] {
            background:
                linear-gradient(180deg, rgba(20, 24, 39, .97), rgba(24, 33, 58, .96)),
                radial-gradient(circle at top, rgba(214, 168, 58, .28), transparent 38%);
            border-right: 1px solid rgba(214, 168, 58, .28);
        }

        [data-testid="stSidebar"] * {
            color: var(--wc-white);
        }

        [data-testid="stSidebar"] [role="radiogroup"] label {
            border-radius: 8px;
            padding: .28rem .42rem;
        }

        [data-testid="stSidebar"] [role="radiogroup"] label:hover {
            background: rgba(214, 168, 58, .14);
        }

        h1, h2, h3 {
            color: var(--wc-white);
            letter-spacing: 0;
        }

        p, label, span, div {
            letter-spacing: 0;
        }

        .wc-app-header {
            min-height: 230px;
            border: 1px solid rgba(214, 168, 58, .46);
            border-radius: 8px;
            background:
                linear-gradient(90deg, rgba(20, 24, 39, .92), rgba(30, 40, 72, .82)),
                radial-gradient(circle at 78% 25%, rgba(35, 215, 215, .25), transparent 30%),
                radial-gradient(circle at 88% 82%, rgba(157, 255, 0, .18), transparent 24%);
            box-shadow: 0 20px 54px rgba(0, 0, 0, .26);
            display: grid;
            grid-template-columns: minmax(120px, 180px) 1fr;
            align-items: center;
            gap: 2rem;
            padding: 2rem;
            margin: .75rem 0 1.5rem;
            overflow: hidden;
            position: relative;
        }

        .wc-header-logo {
            width: 100%;
            max-width: 170px;
            aspect-ratio: 1;
            object-fit: contain;
            justify-self: center;
            filter: drop-shadow(0 16px 32px rgba(0, 0, 0, .52));
        }

        .wc-header-title {
            color: var(--wc-white);
            font-size: 4rem;
            font-weight: 950;
            line-height: .95;
            margin: 0;
            text-shadow: 0 3px 20px rgba(0, 0, 0, .55);
        }

        [class*="st-key-header_nav"] {
            margin: -6.25rem 0 4.6rem 244px;
            max-width: 840px;
            padding: 0;
            position: relative;
            z-index: 2;
        }

        [class*="st-key-nav_"] button {
            background: transparent !important;
            background-color: transparent !important;
            border: 0 !important;
            box-shadow: none !important;
            color: var(--wc-gold) !important;
            text-decoration: none !important;
            font-weight: 900;
            font-size: .84rem;
            line-height: 1;
            border-radius: 0;
            padding: .28rem .02rem;
            text-transform: uppercase;
            letter-spacing: .025em;
            font-family: "Trebuchet MS", "Segoe UI", Arial, sans-serif;
            text-shadow: 0 1px 10px rgba(214, 168, 58, .28);
            transition: background .15s ease, transform .15s ease, text-shadow .15s ease;
            min-height: auto;
            cursor: pointer;
            white-space: nowrap;
        }

        [class*="st-key-nav_"] button:hover,
        [class*="st-key-nav_"] button:focus,
        [class*="st-key-nav_"] button:active {
            background: transparent !important;
            background-color: transparent !important;
            border: 0 !important;
            box-shadow: none !important;
            color: var(--wc-deep-gold) !important;
            text-decoration: none !important;
            transform: translateY(-1px);
            text-shadow: 0 1px 10px rgba(158, 116, 32, .36);
        }

        [class*="st-key-nav_"] button p,
        [class*="st-key-nav_"] button:hover p,
        [class*="st-key-nav_"] button:focus p,
        [class*="st-key-nav_"] button:active p {
            color: var(--wc-gold) !important;
            text-decoration: none !important;
            font-weight: 900;
            white-space: nowrap;
        }

        [class*="st-key-nav_"] button:hover p,
        [class*="st-key-nav_"] button:focus p,
        [class*="st-key-nav_"] button:active p {
            color: var(--wc-deep-gold) !important;
        }

        .wc-sidebar-brand {
            text-align: center;
            padding: .6rem .2rem 1rem;
        }

        .wc-sidebar-logo {
            width: 118px;
            max-width: 75%;
            object-fit: contain;
            margin: 0 auto .65rem;
            display: block;
            filter: drop-shadow(0 10px 24px rgba(0, 0, 0, .46));
        }

        .wc-sidebar-title {
            color: var(--wc-gold);
            font-size: 1.2rem;
            font-weight: 950;
            text-transform: uppercase;
        }

        [data-testid="stSidebar"] button,
        [data-testid="stSidebar"] button:focus,
        [data-testid="stSidebar"] button:active,
        [data-testid="stSidebar"] button:hover {
            background: rgba(5, 5, 5, .46) !important;
            border-color: rgba(214, 168, 58, .35) !important;
            color: var(--wc-gold) !important;
            box-shadow: none !important;
        }

        [data-testid="stSidebar"] button p,
        [data-testid="stSidebar"] button:focus p,
        [data-testid="stSidebar"] button:active p,
        [data-testid="stSidebar"] button:hover p {
            color: var(--wc-gold) !important;
        }

        [data-testid="stSidebar"] a,
        [data-testid="stSidebar"] a:hover,
        [data-testid="stSidebar"] a:focus,
        [data-testid="stSidebar"] a:active {
            background: transparent !important;
            color: var(--wc-gold) !important;
        }

        [data-testid="stSidebar"] [data-testid="stExpander"] details,
        [data-testid="stSidebar"] [data-testid="stExpander"] details[open] {
            background: rgba(5, 5, 5, .38) !important;
            border-color: rgba(214, 168, 58, .28) !important;
        }

        [data-testid="stSidebar"] [data-testid="stExpander"] summary,
        [data-testid="stSidebar"] [data-testid="stExpander"] details[open] summary,
        [data-testid="stSidebar"] [data-testid="stExpander"] summary:hover,
        [data-testid="stSidebar"] [data-testid="stExpander"] summary:focus,
        [data-testid="stSidebar"] [data-testid="stExpander"] summary:active {
            background: rgba(5, 5, 5, .54) !important;
            color: var(--wc-gold) !important;
            box-shadow: none !important;
        }

        [data-testid="stSidebar"] [data-testid="stExpander"] summary *,
        [data-testid="stSidebar"] [data-testid="stExpander"] details[open] summary * {
            color: var(--wc-gold) !important;
        }

        [data-testid="stSidebar"] [data-testid="stExpander"] svg {
            color: var(--wc-gold) !important;
            fill: var(--wc-gold) !important;
        }

        .wc-api-credits {
            border: 1px solid rgba(214, 168, 58, .24);
            border-radius: 8px;
            background: rgba(5, 5, 5, .32);
            margin-top: .85rem;
            padding: .75rem .8rem;
        }

        .wc-api-credits span {
            color: var(--wc-gold);
            display: block;
            font-size: .72rem;
            font-weight: 950;
            text-transform: uppercase;
        }

        .wc-api-credits strong {
            color: var(--wc-white);
            display: block;
            font-size: 1.25rem;
            font-weight: 950;
            line-height: 1.1;
            margin-top: .2rem;
        }

        .wc-api-credits small {
            color: rgba(255,255,255,.62);
            display: block;
            font-size: .68rem;
            font-weight: 750;
            margin-top: .25rem;
        }

        .stButton > button, .stDownloadButton > button {
            background: linear-gradient(135deg, var(--wc-gold), var(--wc-deep-gold));
            color: var(--wc-black);
            border: 1px solid rgba(255, 255, 255, .18);
            border-radius: 8px;
            font-weight: 850;
            box-shadow: 0 8px 20px rgba(0, 0, 0, .20);
        }

        .stButton > button:hover, .stDownloadButton > button:hover {
            border-color: var(--wc-cyan);
            color: var(--wc-black);
            transform: translateY(-1px);
        }

        [data-testid="stMetric"], [data-testid="stDataFrame"], .stAlert {
            border-radius: 8px;
        }

        [data-testid="stDataFrame"] {
            border: 1px solid rgba(214, 168, 58, .18);
            box-shadow: 0 10px 26px rgba(0, 0, 0, .14);
        }

        img[src*="flagcdn.com"] {
            background: #FFFFFF;
            box-sizing: border-box;
            display: block;
            object-fit: cover;
            object-position: center;
        }

        .stTabs [data-baseweb="tab-list"] {
            gap: .35rem;
            border-bottom: 1px solid rgba(214, 168, 58, .22);
        }

        .stTabs [data-baseweb="tab"] {
            background: rgba(255, 255, 255, .10);
            border-radius: 8px 8px 0 0;
            color: var(--wc-white);
            font-weight: 800;
        }

        @media (max-width: 760px) {
            .wc-app-header {
                grid-template-columns: 1fr;
                text-align: center;
                padding: 1.4rem;
            }

        .wc-header-title {
                font-size: 2.6rem;
            }

            [class*="st-key-header_nav"] {
                margin: -1rem 0 1.5rem;
                max-width: none;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_app_header(logo_uri: str | None) -> None:
    logo_markup = (
        f'<img class="wc-header-logo" src="{logo_uri}" alt="World Cup 2026 logo">'
        if logo_uri
        else '<div class="wc-header-logo"></div>'
    )
    st.markdown(
        f"""
        <section class="wc-app-header">
            {logo_markup}
            <div>
                <h1 class="wc-header-title">World Cup 2026 Hub</h1>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _render_header_nav() -> None:
    with st.container(key="header_nav"):
        columns = st.columns([.62, .82, .7, .78, .92, .72, .52, 1.16, .56, .78], gap="small")
        for index, page_name in enumerate(NAV_PAGES):
            with columns[index]:
                label = NAV_LABELS.get(page_name, page_name)
                if st.button(label, key=f"nav_{PAGE_SLUGS[page_name]}", use_container_width=False):
                    st.session_state["page_name"] = page_name
                    clear_detail_origins()
                    st.session_state.pop("selected_team_id", None)
                    st.session_state.pop("selected_match_id", None)
                    st.session_state.pop("selected_fixture_id", None)
                    st.session_state.pop("selected_fixture_row", None)
                    if "team_id" in st.query_params:
                        del st.query_params["team_id"]
                    if "fixture" in st.query_params:
                        del st.query_params["fixture"]
                    st.query_params["page"] = PAGE_SLUGS[page_name]
                    st.rerun()


def _render_sidebar_brand(logo_uri: str | None) -> None:
    logo_markup = (
        f'<img class="wc-sidebar-logo" src="{logo_uri}" alt="World Cup 2026 logo">'
        if logo_uri
        else ""
    )
    st.sidebar.markdown(
        f"""
        <div class="wc-sidebar-brand">
            {logo_markup}
            <div class="wc-sidebar-title">World Cup 2026 Hub</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _require_password() -> None:
    password = get_secret("APP_PASSWORD", default="")
    if not password:
        st.session_state["app_authenticated"] = True
        return
    if st.session_state.get("app_authenticated"):
        return

    st.title("World Cup 2026 Hub")
    st.caption("This shared dashboard is password protected.")
    entered = st.text_input("Password", type="password", key="app_password_input")
    if st.button("Unlock", type="primary"):
        if hmac.compare_digest(entered, password):
            st.session_state["app_authenticated"] = True
            st.rerun()
        st.error("That password did not work.")
    st.stop()


def _render_logout_control() -> None:
    if not get_secret("APP_PASSWORD", default=""):
        return
    if st.sidebar.button("Log out", use_container_width=True):
        st.session_state.pop("app_authenticated", None)
        st.session_state.pop("app_password_input", None)
        st.rerun()


def _prepare_local_data_store() -> None:
    try:
        ensure_app_directories()
        initialize_database()
        # Always reload when committed snapshots are present. load_core_snapshots()
        # no-ops internally unless the snapshot hash changed, so this is cheap and
        # ensures the hosted app picks up updated CSVs without relying on
        # is_deployed() env detection (which Streamlit Community Cloud doesn't set).
        if core_snapshots_available():
            load_core_snapshots()
        if not is_shared_core_read_only_mode() or _core_data_is_empty():
            seed_world_cup_2026_reference_data()
        _refresh_daily_odds_on_app_entry()
    except Exception as exc:
        st.error(f"Could not prepare the local data store: {exc}")
        st.stop()


def _refresh_daily_odds_on_app_entry() -> None:
    if is_shared_core_read_only_mode():
        return
    refresh_key = daily_odds_refresh_key()
    tournament_result = refresh_tournament_odds_if_available(refresh_key)
    match_result = refresh_match_odds_if_available(refresh_key)
    if tournament_result.get("saved"):
        latest_tournament_winner_odds.clear()
    if tournament_result.get("error"):
        st.sidebar.warning(tournament_result["error"])
    if match_result.get("error"):
        st.sidebar.warning(match_result["error"])


def _core_data_is_empty() -> bool:
    try:
        teams = fetch_df("SELECT COUNT(*) AS count FROM teams")
        return teams.empty or int(teams.iloc[0]["count"] or 0) == 0
    except Exception:
        return True


def _render_mode_status() -> None:
    config = get_app_config()
    if config.shared_core_read_only_mode:
        st.sidebar.info("Shared mode")
        st.sidebar.caption("Favorites and picks are saved on this browser/device.")
    if preferences_are_session_only():
        st.sidebar.warning("Personal preferences are saved for this session only.")


def _render_browser_preference_controls() -> None:
    with st.sidebar.expander("Browser preferences", expanded=False):
        st.caption(
            "No account is required. Preferences stay with this browser/device and may not carry across devices, "
            "private windows, cleared site data, or app URL changes."
        )
        if st.button("Clear saved preferences", use_container_width=True):
            clear_browser_preferences()
            st.success("Saved browser preferences cleared.")
            st.rerun()


CENTRAL_TZ = ZoneInfo("America/Chicago")


def _format_central(updated: str) -> str:
    """Render a stored UTC timestamp (SQLite CURRENT_TIMESTAMP) in Central time."""
    text = str(updated).strip()
    if not text:
        return ""
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return text
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    local = parsed.astimezone(CENTRAL_TZ)
    hour12 = local.strftime("%I").lstrip("0") or "12"
    tzname = local.strftime("%Z") or "CT"
    return f"{local.strftime('%b')} {local.day}, {local.year} {hour12}:{local.strftime('%M')} {local.strftime('%p')} {tzname}"


def _render_score_refresh_control() -> None:
    """Sidebar button to force a fresh football-data.org pull on the next render."""
    if is_shared_core_read_only_mode():
        st.sidebar.caption("Shared mode: manual refresh is disabled.")
        return
    if st.sidebar.button("Refresh scores now", use_container_width=True):
        # Clear the football-data fetch caches AND every page-level cache that
        # derives standings/scoreboards from them. Clearing only the fetch caches
        # leaves the derived caches serving stale tables (they never re-call the
        # API), so the page would not visibly update. The Odds API is unaffected:
        # its refresh is gated in the database, not by st.cache_data.
        clear_football_data_cache()
        st.cache_data.clear()
        st.sidebar.success("Pulling fresh scores from football-data.org…")


def _api_usage_box(label: str, provider: str) -> str:
    usage = fetch_df(
        """
        SELECT requests_remaining, requests_used, updated_at
        FROM api_usage
        WHERE provider = ?
        ORDER BY datetime(updated_at) DESC, id DESC
        LIMIT 1
        """,
        [provider],
    )
    if usage.empty:
        remaining = "not checked yet"
        updated = ""
    else:
        row = usage.iloc[0]
        remaining = row["requests_remaining"] or "unavailable"
        updated = _format_central(row["updated_at"] or "")
    updated_markup = f"<small>Updated {updated}</small>" if updated else ""
    return (
        '<div class="wc-api-credits">'
        f'<span>{label}</span>'
        f'<strong>{remaining}</strong>'
        f'{updated_markup}'
        '</div>'
    )


_apply_theme()
render_browser_preferences_bridge()
_require_password()
_prepare_local_data_store()
logo_uri = _logo_data_uri()

if logo_uri is None:
    st.warning("Logo file not found. Add it to assets/world_cup_2026_logo.png")

requested_page = st.session_state.pop("requested_page", None)
requested_page = PAGE_ALIASES.get(requested_page, requested_page)
query_page = SLUG_TO_PAGE.get(str(st.query_params.get("page", "")).strip())
if requested_page in PAGES:
    st.session_state["page_name"] = requested_page
    st.query_params["page"] = PAGE_SLUGS.get(requested_page, PAGE_SLUGS["Home"])
elif query_page in PAGES:
    st.session_state["page_name"] = query_page
if "page_name" not in st.session_state or st.session_state["page_name"] not in PAGES:
    st.session_state["page_name"] = list(PAGES.keys())[0]
page_name = st.session_state["page_name"]

_render_app_header(logo_uri)
_render_header_nav()
_render_mode_status()
page_name = st.session_state["page_name"]
_render_sidebar_brand(logo_uri)
_render_logout_control()
_render_browser_preference_controls()
previous_page_name = st.session_state.get("_previous_page_name")
if page_name == "Teams" and previous_page_name not in (None, "Teams"):
    st.session_state.pop("selected_team_id", None)
    st.session_state.pop("selected_match_id", None)
team_id_param = st.query_params.get("team_id")
if page_name == "Teams" and team_id_param:
    try:
        st.session_state["selected_team_id"] = int(team_id_param[0] if isinstance(team_id_param, list) else team_id_param)
        st.session_state.pop("selected_match_id", None)
    except (TypeError, ValueError):
        pass
st.session_state["_previous_page_name"] = page_name
st.sidebar.divider()
st.sidebar.markdown(_api_usage_box("football-data.org credits", "football_data_org"), unsafe_allow_html=True)
st.sidebar.markdown(_api_usage_box("Odds API credits", "the_odds_api"), unsafe_allow_html=True)
_render_score_refresh_control()

PAGES[page_name]()


components.html(
    f"""
    <script>
    (() => {{
      const pageName = {page_name!r};
      const doc = window.parent.document;
      const sidebarSelector = '[data-testid="stSidebar"]';
      const openControlSelector = '[data-testid="collapsedControl"]';
      const collapseButtonSelectors = [
        '[data-testid="stSidebarCollapseButton"] button',
        '[data-testid="stSidebar"] button[title*="collapse" i]',
        '[data-testid="stSidebar"] button[aria-label*="collapse" i]',
        '[data-testid="stSidebar"] button[title*="close" i]',
        '[data-testid="stSidebar"] button[aria-label*="close" i]'
      ];

      function sidebar() {{
        return doc.querySelector(sidebarSelector);
      }}

      function sidebarIsOpen() {{
        const element = sidebar();
        return Boolean(element && element.getBoundingClientRect().width > 120);
      }}

      function collapseButton() {{
        for (const selector of collapseButtonSelectors) {{
          const button = doc.querySelector(selector);
          if (button) {{
            return button;
          }}
        }}
        return null;
      }}

      function collapseSidebar() {{
        if (!sidebarIsOpen()) {{
          return;
        }}
        const button = collapseButton();
        if (button) {{
          button.click();
        }}
      }}

      const previousPage = window.sessionStorage.getItem("wc2026PageName");
      window.sessionStorage.setItem("wc2026PageName", pageName);
      if (previousPage && previousPage !== pageName) {{
        window.setTimeout(collapseSidebar, 250);
      }}

      if (!window.wc2026SidebarAutoCloseBound) {{
        window.wc2026SidebarAutoCloseBound = true;
        doc.addEventListener(
          "pointerdown",
          (event) => {{
            const element = sidebar();
            const openControl = doc.querySelector(openControlSelector);
            if (!element || !sidebarIsOpen()) {{
              return;
            }}
            if (element.contains(event.target) || (openControl && openControl.contains(event.target))) {{
              return;
            }}
            window.setTimeout(collapseSidebar, 0);
          }},
          true
        );
      }}
    }})();
    </script>
    """,
    height=0,
)

