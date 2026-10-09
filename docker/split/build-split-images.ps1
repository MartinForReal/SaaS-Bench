$ErrorActionPreference = "Continue"
$root = "C:\Users\shafan\copilotlumina\SaaS-Bench"
$reg = "luminaevalsaasbenchregistry-cag8c5axaeetd5cj.azurecr.io/saas-bench"
$tag = "20261008-953b1ecbea0e"
$builds = @(
  @{Repo="mw-twenty-redis"; Df="docker/split/mw-twenty/Dockerfile.redis"; Ctx="docker/split/mw-twenty"; Base="mw-twenty"},
  @{Repo="mw-twenty-app";   Df="docker/split/mw-twenty/Dockerfile.app";   Ctx="docker/split/mw-twenty"; Base="mw-twenty"},
  @{Repo="mw-booklore-db";  Df="docker/split/mw-booklore/Dockerfile.db";  Ctx="docker/split/mw-booklore"; Base="mw-booklore"},
  @{Repo="mw-booklore-app"; Df="docker/split/mw-booklore/Dockerfile.app"; Ctx="docker/split/mw-booklore"; Base="mw-booklore"},
  @{Repo="mw-hrms-db";      Df="docker/split/mw-hrms/Dockerfile.db";      Ctx="docker/split/mw-hrms"; Base="mw-hrms"},
  @{Repo="mw-hrms-redis";   Df="docker/split/mw-hrms/Dockerfile.redis";   Ctx="docker/split/mw-hrms"; Base="mw-hrms"},
  @{Repo="mw-hrms-app";     Df="docker/split/mw-hrms/Dockerfile.app";     Ctx="docker/split/mw-hrms"; Base="mw-hrms"},
  @{Repo="mw-pretix-db";    Df="docker/split/mw-pretix/Dockerfile.db";    Ctx="docker/split/mw-pretix"; Base="mw-pretix"},
  @{Repo="mw-pretix-redis"; Df="docker/split/mw-pretix/Dockerfile.redis"; Ctx="docker/split/mw-pretix"; Base="mw-pretix"},
  @{Repo="mw-pretix-web";   Df="docker/split/mw-pretix/Dockerfile.web";   Ctx="docker/split/mw-pretix"; Base="mw-pretix"},
  @{Repo="mw-pretix-task";  Df="docker/split/mw-pretix/Dockerfile.task";  Ctx="docker/split/mw-pretix"; Base="mw-pretix"},
  @{Repo="mw-pretix-nginx"; Df="docker/split/mw-pretix/Dockerfile.nginx"; Ctx="docker/split/mw-pretix"; Base="mw-pretix"},
  @{Repo="mw-opnform-db";   Df="docker/split/mw-opnform/Dockerfile.db";   Ctx="docker/split/mw-opnform"; Base="mw-opnform"},
  @{Repo="mw-opnform-redis";Df="docker/split/mw-opnform/Dockerfile.redis";Ctx="docker/split/mw-opnform"; Base="mw-opnform"},
  @{Repo="mw-opnform-app";  Df="docker/split/mw-opnform/Dockerfile.app";  Ctx="docker/split/mw-opnform"; Base="mw-opnform"}
)
$max = 5
$jobs = @()
foreach ($b in $builds) {
  while ((@($jobs | Where-Object { $_.State -eq "Running" }).Count) -ge $max) { Start-Sleep -Seconds 5 }
  $jobs += Start-Job -ScriptBlock {
    param($b, $reg, $tag, $root)
    Set-Location $root
    $img = "$reg/$($b.Repo):$tag"
    $out = docker buildx build --builder aks-buildkit --platform linux/amd64 --provenance=false --sbom=false --push -t $img --build-arg "BASE_IMAGE=$reg/$($b.Base):$tag" -f $b.Df $b.Ctx 2>&1 | Select-Object -Last 3
    "$($b.Repo) EXIT=$LASTEXITCODE :: " + ($out -join " | ")
  } -ArgumentList $b, $reg, $tag, $root
}
$jobs | Wait-Job | Out-Null
$jobs | Receive-Job
$jobs | Remove-Job
Write-Output "SPLIT_BUILD_DONE"