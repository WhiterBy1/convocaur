from fastapi import APIRouter

from app.services.data import load_dashboard, matching_summary, project_stats

router = APIRouter(tags=["overview"])


@router.get("/overview")
def overview() -> dict:
    dash = load_dashboard()
    match = matching_summary()
    stats = project_stats()
    return {
        "brand": "ConvocaUR",
        "tagline": "Inteligencia de contratación CTeI y matching de talento Rosario",
        "stats": stats,
        "secop_resumen": {
            "universo": dash.get("universo"),
            "cap3_auc": dash.get("capacidad_3", {})
            .get("adjudicacion_competitivo", {})
            .get("auc_roc"),
            "hhi_corregido": dash.get("capacidad_2", {}).get("hhi", {}).get("despues_correccion"),
            "unspsc_mix": dash.get("capacidad_1", {}).get("unspsc_mix"),
        },
        "matching_resumen": match,
    }
