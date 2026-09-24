from saas_bench.k8s_slot import K8sSlotManager
from saas_bench.targets import K8sTarget, make_target
from saas_bench.verify_runner import _build_k8s_exec_map


def test_make_target_selects_k8s_backend():
    target = make_target("k8s", {"code-server": {"app_index": 0}}, 0, "localhost", True)
    assert isinstance(target, K8sTarget)
    assert isinstance(target._slot, K8sSlotManager)


def test_k8s_exec_map_uses_namespace_prefix(monkeypatch):
    monkeypatch.setenv("SAAS_K8S_NAMESPACE_PREFIX", "saasbench-s2")
    mapping = _build_k8s_exec_map(["code-server"], 2)

    assert mapping["rollout_2_code-server"] == {
        "namespace": "saasbench-s2-code-server",
        "selector": "app=code-server",
        "container": "code-server",
    }
