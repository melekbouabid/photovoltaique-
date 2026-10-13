"""Contrats de données (Pandera) : une table qui ne respecte pas son schéma arrête le pipeline."""
from __future__ import annotations

import pandas as pd

try:                                    # pandera >= 0.24 range l'API pandas dans un sous-module
    import pandera.pandas as pa
except ImportError:                     # versions antérieures
    import pandera as pa

from solarvision.data.process import IMPUTED, expected_days, pv_columns

# Borne physique large : 1 kWc ne peut pas produire plus de 24 kWh en un jour, et jamais moins de zéro.
MAX_DAILY_KWH_PER_KWP = 12.0
MAX_DAILY_IRRADIATION_KWH_M2 = 15.0


def processed_schema() -> pa.DataFrameSchema:
    """Table traitée d'une ville : trois séries PV complètes, positives, et le drapeau d'imputation."""
    columns = {c: pa.Column(float, pa.Check.in_range(0, MAX_DAILY_KWH_PER_KWP), nullable=False) for c in pv_columns()}
    columns[IMPUTED] = pa.Column(int, pa.Check.isin([0, 1]), nullable=False)
    return pa.DataFrameSchema(
        columns, strict=True, index=pa.Index("datetime64[ns]", unique=True, name="date"),
        checks=[pa.Check(lambda d: len(d) == expected_days(), error=f"{expected_days()} lignes attendues"),
                pa.Check(lambda d: bool((d.index.to_series().diff().dropna() == pd.Timedelta(days=1)).all()),
                         error="dates continues attendues")])


def interim_schema() -> pa.DataFrameSchema:
    """Table complète d'une ville : les sources indépendantes doivent être présentes et plausibles."""
    irradiation = pa.Check.in_range(0, MAX_DAILY_IRRADIATION_KWH_M2)
    return pa.DataFrameSchema({
        **{c: pa.Column(float, pa.Check.in_range(0, MAX_DAILY_KWH_PER_KWP), nullable=False) for c in pv_columns()},
        "ghi_pvgis_kwh_m2": pa.Column(float, irradiation, nullable=False),
        "ghi_nasa_kwh_m2": pa.Column(float, irradiation, nullable=True),
        "ghi_era5_kwh_m2": pa.Column(float, irradiation, nullable=True),
        "nebulosite_pct": pa.Column(float, pa.Check.in_range(0, 100), nullable=True),
        "t2m_moy_c": pa.Column(float, pa.Check.in_range(-40, 55), nullable=False),
        "hauteur_soleil_midi_deg": pa.Column(float, pa.Check.in_range(0, 90), nullable=False),
        IMPUTED: pa.Column(int, pa.Check.isin([0, 1]), nullable=False),
    }, strict=False)


def validate_city_tables(daily: pd.DataFrame) -> None:
    """Lève une erreur Pandera si la table d'une ville viole un contrat."""
    interim_schema().validate(daily, lazy=True)
    processed_schema().validate(daily[[*pv_columns(), IMPUTED]], lazy=True)
