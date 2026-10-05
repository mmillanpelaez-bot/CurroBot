import unittest
from filter_engine import JobOffer, create_job_filter_from_config


class TestDualModeFiltering(unittest.TestCase):

    def setUp(self):
        self.sample_offers: list[JobOffer] = [
            {
                "id": "1",
                "title": "Desarrollador Python Junior",
                "company": "Company A",
                "location": "Remoto",
                "url": "https://example.com/1",
                "source": "Tecnoempleo",
                "published_at": "2026-10-01 10:00",
            },
            {
                "id": "2",
                "title": "Frontend React Developer",
                "company": "Company B",
                "location": "Madrid",
                "url": "https://example.com/2",
                "source": "RemoteOK",
                "published_at": "2026-10-01 11:00",
            },
        ]
        self.base_config = {
            "forbidden_keywords": ["senior"],
            "required_keywords": ["python"]
        }

    def test_default_base_config_mode(self):
        """Modo 1: Usa la configuración base guardada sin sobreescrituras."""
        engine = create_job_filter_from_config(config_source=self.base_config)
        filtered = engine.filter_offers(self.sample_offers)

        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["id"], "1")

    def test_runtime_override_mode(self):
        """Modo 2: El usuario solicita cambiar criterios dinámicamente en tiempo de ejecución."""
        ad_hoc_request = {
            "required_keywords": ["react"]
        }
        engine = create_job_filter_from_config(
            config_source=self.base_config,
            runtime_overrides=ad_hoc_request
        )
        filtered = engine.filter_offers(self.sample_offers)

        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["id"], "2")


if __name__ == "__main__":
    unittest.main()