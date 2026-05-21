from __future__ import annotations

import csv
import html
from io import StringIO

import streamlit as st


WORLD_CUP_HISTORY_CSV = """Year,World Cup winner,World Cup Runner Up,World Cup Third Place
1930,Uruguay,Argentina,United States
1934,Italy,Czechoslovakia,Germany
1938,Italy,Hungary,Brazil
1950,Uruguay,Brazil,Sweden
1954,West Germany,Hungary,Austria
1958,Brazil,Sweden,France
1962,Brazil,Czechoslovakia,Chile
1966,England,West Germany,Portugal
1970,Brazil,Italy,West Germany
1974,West Germany,Netherlands,Poland
1978,Argentina,Netherlands,Brazil
1982,Italy,West Germany,Poland
1986,Argentina,West Germany,France
1990,West Germany,Argentina,Italy
1994,Brazil,Italy,Sweden
1998,France,Brazil,Croatia
2002,Brazil,Germany,Turkey
2006,Italy,France,Germany
2010,Spain,Netherlands,Germany
2014,Germany,Argentina,Netherlands
2018,France,Croatia,Belgium
2022,Argentina,France,Croatia
"""


def render() -> None:
    st.title("History")
    _styles()
    rows = _history_rows()
    st.markdown(_history_table(rows), unsafe_allow_html=True)


def _history_rows() -> list[dict[str, str]]:
    rows = list(csv.DictReader(StringIO(WORLD_CUP_HISTORY_CSV)))
    return sorted(rows, key=lambda row: int(row["Year"]), reverse=True)


def _history_table(rows: list[dict[str, str]]) -> str:
    body = "".join(_history_row(row) for row in rows)
    return f"""
    <section class="history-shell">
      <div class="history-table-wrap">
        <table class="history-table">
          <thead>
            <tr>
              <th>Year</th>
              <th>Winner</th>
              <th>Runner Up</th>
              <th>Third Place</th>
            </tr>
          </thead>
          <tbody>{body}</tbody>
        </table>
      </div>
    </section>
    """


def _history_row(row: dict[str, str]) -> str:
    return (
        "<tr>"
        f"<td><span>{html.escape(row['Year'])}</span></td>"
        f"<td><strong>{html.escape(row['World Cup winner'])}</strong></td>"
        f"<td>{html.escape(row['World Cup Runner Up'])}</td>"
        f"<td>{html.escape(row['World Cup Third Place'])}</td>"
        "</tr>"
    )


def _styles() -> None:
    st.markdown(
        """
        <style>
        .history-shell {
            margin-top: .8rem;
        }
        .history-table-wrap {
            border: 1px solid rgba(214,168,58,.24);
            border-radius: 8px;
            background:
                linear-gradient(135deg, rgba(5,5,5,.58), rgba(11,16,32,.52)),
                radial-gradient(circle at 100% 0%, rgba(36,88,255,.14), transparent 34%);
            box-shadow: 0 18px 44px rgba(0,0,0,.24);
            overflow-x: auto;
        }
        .history-table {
            border-collapse: collapse;
            min-width: 720px;
            width: 100%;
        }
        .history-table th {
            border-bottom: 1px solid rgba(214,168,58,.34);
            color: #D6A83A;
            font-size: .72rem;
            font-weight: 950;
            padding: .85rem .95rem;
            text-align: left;
            text-transform: uppercase;
        }
        .history-table td {
            border-bottom: 1px solid rgba(255,255,255,.08);
            color: #E5E7EB;
            font-weight: 800;
            padding: .78rem .95rem;
        }
        .history-table tr:last-child td {
            border-bottom: 0;
        }
        .history-table tbody tr:nth-child(odd) td {
            background: rgba(255,255,255,.035);
        }
        .history-table td span {
            color: #D6A83A;
            font-weight: 950;
        }
        .history-table td strong {
            color: #FFFFFF;
            font-weight: 950;
        }
        @media (max-width: 760px) {
            .history-table th,
            .history-table td {
                padding: .7rem .78rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
