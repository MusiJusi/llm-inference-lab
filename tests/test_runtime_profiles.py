import unittest
from scripts.runtime import cache_mount_argument,compose_command,validate_running_model

class RuntimeProfileTests(unittest.TestCase):
    def fixture(self):
        return {"services":{"server":{"environment":{"MODEL_ID":"Qwen/example","MODEL_REVISION":"a"*40,"MODEL_ROOT":"/models"}},"download-model":{"volumes":[{"type":"bind","source":"D:/lab/models","target":"/models"}]}},"volumes":{"models":{"name":"llm-inference-lab-models"}}}

    def test_wrong_running_model_is_rejected(self):
        configuration=self.fixture()
        details={"State":{"Running":True},"Config":{"Env":["MODEL_ID=Qwen/other","MODEL_REVISION="+"a"*40,"MODEL_ROOT=/models"]}}
        with self.assertRaises(RuntimeError):validate_running_model(configuration,details)

    def test_offline_cache_follows_bind_or_named_volume(self):
        configuration=self.fixture()
        self.assertEqual(cache_mount_argument(configuration),"type=bind,src=D:/lab/models,dst=/models")
        configuration["services"]["download-model"]["volumes"][0]={"type":"volume","source":"models","target":"/models"}
        self.assertEqual(cache_mount_argument(configuration),"type=volume,src=llm-inference-lab-models,dst=/models")

    def test_unknown_profile_cannot_read_an_unrelated_compose_file(self):
        with self.assertRaises(ValueError):compose_command("../../other-project")
