import marimo

__generated_with = "0.17.6"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import polars as pl
    from pathlib import Path
    from datetime import datetime
    return Path, datetime, mo, pl


@app.cell
def _(mo):
    mo.md(r"""
    The collected revisions data is currently nested, with up to 500 revisions in each row; we want each revision to have its own row.
    """)
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## Reformat Revisions Data
    """)
    return


@app.cell
def _(mo):
    mo.md(r"""
    Load in the data.
    """)
    return


@app.cell
def _(Path, pl):
    ROOT = Path.cwd()
    if ROOT.name == 'notebooks':
        ROOT = ROOT.parent

    rev_df_raw = pl.read_parquet(ROOT / "data" / "raw" / "revision_results_df_raw.parquet")
    rev_df_raw
    return ROOT, rev_df_raw


@app.cell
def _(mo):
    mo.md(r"""
    Unnest the data. The raw data will be split into chunks to make the amount of time spent unnesting it more manageable.
    """)
    return


@app.cell
def _(datetime, pl):
    def unnest_data(df):
        """ Pull out each revision and turn it into its own row. """
        records = [] # Create a list of dictionaries that will later be turned into a dataframe

        for row in df.iter_rows(named=True):
            title = row['title']
            # print(f'Extracting rows for {title}...')

            for i in range(len(row['revision_ids'])):
                # Extract each revision into its own row
                records.append({
                    'title': title,
                    'user': row['users'][i],
                    'rev_id': row['revision_ids'][i],
                    'timestamp': datetime.fromisoformat(
                        row['timestamps'][i].replace('Z', '+00:00')),
                    'size': row['sizes'][i],
                    'size_delta': row['size_deltas'][i]
                })

        rev_schema = {'title': pl.String, 'user': pl.String, 
                      'rev_id': pl.Int64, 'timestamp': pl.Datetime("us", "UTC"), 
                      'size': pl.Int64, 'size_delta': pl.Int64}

        return pl.DataFrame(records, schema=rev_schema)
    return (unnest_data,)


@app.cell
def _(rev_df_raw):
    # Split the raw dataset into 3 subsections
    raw_data_a = rev_df_raw[:355] 
    raw_data_b = rev_df_raw[355:709]
    raw_data_c = rev_df_raw[709:]
    return raw_data_a, raw_data_b, raw_data_c


@app.cell
def _(raw_data_a, unnest_data):
    # Unnest the data from each chunk
    rev_df_a = unnest_data(raw_data_a)
    return (rev_df_a,)


@app.cell
def _(raw_data_b, unnest_data):
    rev_df_b = unnest_data(raw_data_b)
    return (rev_df_b,)


@app.cell
def _(raw_data_c, unnest_data):
    rev_df_c = unnest_data(raw_data_c)
    return (rev_df_c,)


@app.cell
def _(mo):
    mo.md(r"""
    Combine into one dataset.
    """)
    return


@app.cell
def _(pl, rev_df_a, rev_df_b, rev_df_c):
    rev_df = pl.concat([rev_df_a, rev_df_b, rev_df_c])
    rev_df
    return (rev_df,)


@app.cell
def _(ROOT, rev_df):
    rev_df.write_parquet(ROOT / "data" / "processed" / "revision_results_df.parquet")
    return


if __name__ == "__main__":
    app.run()
