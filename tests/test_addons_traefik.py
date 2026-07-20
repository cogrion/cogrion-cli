from cogrion_cli.bootstrap.addons import make_traefik


def test_make_traefik_sets_http_to_https_redirect():
    addon = make_traefik("subnet-aaa111,subnet-bbb222")

    # Regression guard: the traefik chart's values schema rejects
    # ports.web.redirections (schema error: "additional properties
    # 'redirections' not allowed") — redirections lives one level
    # deeper, under ports.web.http.
    assert addon.set_args["ports.web.http.redirections.entryPoint.to"] == "websecure"
    assert addon.set_args["ports.web.http.redirections.entryPoint.scheme"] == "https"
    assert addon.set_args["ports.web.http.redirections.entryPoint.permanent"] == "true"
    assert "ports.web.redirections.entryPoint.to" not in addon.set_args


def test_make_traefik_keeps_subnet_annotation():
    addon = make_traefik("subnet-aaa111,subnet-bbb222")

    key = "service.annotations.service\\.beta\\.kubernetes\\.io/aws-load-balancer-subnets"
    assert addon.set_args[key] == "subnet-aaa111,subnet-bbb222"


def test_make_traefik_does_not_strip_space_after_comma():
    # make_traefik passes public_subnets straight through with no normalization
    # — a "subnet-a, subnet-b" (space after comma) input keeps that space, and
    # nothing downstream (helm.py's --set escaping only backslash-escapes the
    # comma itself) trims it either. AWS subnet-ID discovery on the resulting
    # annotation value is whitespace-sensitive, so a leading space would make
    # the second subnet ID unrecognizable. Documents current behavior — not
    # asserting this is desirable, just pinning it so a future fix is visible
    # as an intentional test change, not a silent behavior shift.
    addon = make_traefik("subnet-aaa111, subnet-bbb222")

    key = "service.annotations.service\\.beta\\.kubernetes\\.io/aws-load-balancer-subnets"
    assert addon.set_args[key] == "subnet-aaa111, subnet-bbb222"
