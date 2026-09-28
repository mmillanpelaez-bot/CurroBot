import json
import os
import tempfile
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional


class PersistenceEngine:
    def __init__(self, filepath: str = "data/seen_jobs.json"):
        self.filepath = filepath
        self.archivo_existe()

    def archivo_existe(self) -> None:
        """Crea el directorio y el archivo inicial si no existen."""
        directory = os.path.dirname(self.filepath)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)

        if not os.path.exists(self.filepath):
            initial_data = {
                "version": "1.0",
                "last_updated": self.fecha_hora_actual(),
                "seen_jobs": {}
            }
            self.cargar_datos(initial_data)

    def fecha_hora_actual(self) -> str:
        """Retorna la fecha y hora actual en formato ISO 8601 UTC."""
        return datetime.now(timezone.utc).isoformat()

    def cargar_datos(self) -> Dict[str, Any]:
        """Carga el contenido completo del JSON. Retorna estructura vacía si hay error."""
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {"version": "1.0", "last_updated": self._get_utc_now(), "seen_jobs": {}}

    def guardar_datos(self, data: Dict[str, Any]) -> None:
        """Guarda los datos de forma atómica usando un archivo temporal."""
        data["last_updated"] = self.fecha_hora_actual()
        dir_name = os.path.dirname(self.filepath) or "."

        # Escritura en archivo temporal y reemplazo atómico para prevenir corrupción
        with tempfile.NamedTemporaryFile("w", dir=dir_name, delete=False, encoding="utf-8") as tf:
            json.dump(data, tf, indent=2, ensure_ascii=False)
            temp_path = tf.name

        os.replace(temp_path, self.filepath)

    def oferta_vista(self, job_id: str) -> bool:
        """Comprobación O(1) para saber si un empleo ya existe."""
        data = self.cargar_datos()
        return job_id in data.get("seen_jobs", {})

    def añadir_oferta(self, job_id: str, job_info: Dict[str, Any]) -> None:
        """Agrega o actualiza un empleo en el registro."""
        data = self.cargar_datos()
        job_entry = {**job_info, "first_seen_at": job_info.get("first_seen_at", self.fecha_hora_actual())}
        data["seen_jobs"][job_id] = job_entry
        self.guardar_datos(data)

    def eliminar_antiguos(self, days: int = 30) -> int:
        """Elimina empleos cuya antigüedad supere los días indicados. Retorna la cantidad eliminada."""
        data = self.cargar_datos()
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        seen_jobs = data.get("seen_jobs", {})

        filtered_jobs = {}
        removed_count = 0

        for j_id, j_data in seen_jobs.items():
            first_seen_str = j_data.get("first_seen_at")
            if first_seen_str:
                job_date = datetime.fromisoformat(first_seen_str)
                if job_date >= cutoff_date:
                    filtered_jobs[j_id] = j_data
                else:
                    removed_count += 1
            else:
                filtered_jobs[j_id] = j_data

        if removed_count > 0:
            data["seen_jobs"] = filtered_jobs
            self.guardar_datos(data)

        return removed_count