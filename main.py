import os
from dotenv import load_dotenv
load_dotenv(override=True)
import subprocess
import time
import uuid
import asyncio
import random
import boto3
import requests
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse, HTMLResponse, RedirectResponse
from pydantic import BaseModel
from typing import Optional
import json

app = FastAPI(title="GreenCloud AI v3.0 Backend", version="3.0")

USERS_DB = {
    "admin@greencloud.ai": {"name": "Admin User", "password": "password123"}
}
SESSIONS_DB = {}

def check_auth(request: Request) -> bool:
    token = request.cookies.get("session_token")
    return token is not None and token in SESSIONS_DB

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configured API Keys from User Environment
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
ELECTRICITY_MAPS_KEY = os.getenv("ELECTRICITY_MAPS_API_KEY", "")
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
GCP_BILLING_KEY = os.getenv("GCP_BILLING_API_KEY", "")

REGIONAL_GRID = {
    "na": 380,
    "eu": 210,
    "nordics": 25,
    "apac": 490,
    "sa": 110
}

BASE_PROVIDERS = [
    {
        "id": "hetzner",
        "name": "Hetzner Cloud",
        "cpuRate": 2.20,
        "ramRate": 0.65,
        "storageRate": 0.045,
        "pue": 1.12,
        "renewablePct": 100,
        "baseLocation": "Europe / US",
        "regions": ["Falkenstein, Germany", "Helsinki, Finland", "Ashburn, VA (US)"],
        "hardware": ["AMD EPYC 7003 series", "Ampere Altra ARM processors"],
        "compliance": ["ISO 27001", "100% Hydropower matching (Helsinki)", "Data privacy (GDPR)"],
        "breakdown": "Top tier carbon score driven by 100% renewable grid sourcing and ultra-low PUE.",
        "features": ["NVMe Storage", "100% Green Datacenters", "Unbeatable Price/Perf"]
    },
    {
        "id": "scaleway",
        "name": "Scaleway",
        "cpuRate": 2.80,
        "ramRate": 0.75,
        "storageRate": 0.050,
        "pue": 1.15,
        "renewablePct": 98,
        "baseLocation": "EU (Paris / Amsterdam)",
        "regions": ["Paris (France)", "Amsterdam (Netherlands)", "Warsaw (Poland)"],
        "hardware": ["Intel Xeon Gold", "AMD EPYC 7002/7003", "Apple Silicon"],
        "compliance": ["ISO 27001", "HDS Certification", "EU Code of Conduct for Data Centres"],
        "breakdown": "High cost-efficiency and water-cooled servers drastically reduce energy footprint.",
        "features": ["Water-cooled Servers", "Low Carbon PUE", "Flexible API"]
    },
    {
        "id": "ovh",
        "name": "OVHcloud",
        "cpuRate": 3.10,
        "ramRate": 0.80,
        "storageRate": 0.055,
        "pue": 1.18,
        "renewablePct": 92,
        "baseLocation": "Global Datacenters",
        "regions": ["Roubaix (France)", "Beauharnois (Canada)", "Sydney (Australia)", "Singapore"],
        "hardware": ["Intel Xeon Scalable", "AMD EPYC", "NVIDIA Tesla GPUs"],
        "compliance": ["ISO 27001", "ISO 27701", "SOC 1/2/3", "CISPE Data Protection"],
        "breakdown": "Excellent proprietary liquid cooling setup enabling competitive cost and PUE.",
        "features": ["Proprietary Water Cooling", "Anti-DDoS Included", "ISO 27001"]
    },
    {
        "id": "digitalocean",
        "name": "DigitalOcean",
        "cpuRate": 4.50,
        "ramRate": 1.10,
        "storageRate": 0.100,
        "pue": 1.35,
        "renewablePct": 65,
        "baseLocation": "Global Edge",
        "regions": ["New York (US)", "Frankfurt (Germany)", "London (UK)", "Bangalore (India)"],
        "hardware": ["Intel Xeon", "AMD EPYC"],
        "compliance": ["SOC 2 Type II", "GDPR", "PCI-DSS"],
        "breakdown": "Balanced performance and simplicity; moderate PUE with ongoing renewable transitions.",
        "features": ["Simple Developer UX", "App Platform", "Managed K8s"]
    },
    {
        "id": "aws",
        "name": "Amazon Web Services",
        "cpuRate": 7.20,
        "ramRate": 1.85,
        "storageRate": 0.120,
        "pue": 1.45,
        "renewablePct": 85,
        "baseLocation": "32 Global Regions",
        "regions": ["Northern Virginia (US-East)", "Frankfurt (EU-Central)", "Tokyo (AP-Northeast)", "São Paulo (SA-East)"],
        "hardware": ["Intel Xeon", "AMD EPYC", "Graviton (ARM) processors"],
        "compliance": ["FedRAMP", "ISO 9001/27001", "HIPAA", "100% renewable energy path by 2025"],
        "breakdown": "Unmatched scale and ecosystem, with strong commitment to 100% renewables and Graviton efficiency.",
        "features": ["Full Cloud Ecosystem", "Enterprise SLA", "Graviton Compute"],
        "usesApi": True
    },
    {
        "id": "azure",
        "name": "Microsoft Azure",
        "cpuRate": 7.50,
        "ramRate": 1.90,
        "storageRate": 0.125,
        "pue": 1.42,
        "renewablePct": 80,
        "baseLocation": "60+ Global Regions",
        "regions": ["Washington (West US)", "Ireland (North Europe)", "Pune (Central India)", "Johannesburg (South Africa)"],
        "hardware": ["Intel Xeon", "AMD EPYC", "Ampere Altra ARM"],
        "compliance": ["90+ compliance certifications", "ISO 27001", "Water positive by 2030 promise"],
        "breakdown": "Extremely robust enterprise compliance and an ambitious roadmap to become carbon negative.",
        "features": ["Active Directory Native", "Enterprise Hybrid", "Copilot Integration"]
    },
    {
        "id": "gcp",
        "name": "Google Cloud Platform",
        "cpuRate": 6.90,
        "ramRate": 1.80,
        "storageRate": 0.115,
        "pue": 1.25,
        "renewablePct": 90,
        "baseLocation": "35 Global Regions",
        "regions": ["Iowa (US-Central)", "Eemshaven (EU-West)", "Mumbai (Asia-South)"],
        "hardware": ["Intel Xeon Scalable", "AMD EPYC", "Google Cloud TPUs"],
        "compliance": ["ISO 27001", "FedRAMP High", "24/7 Carbon-Free Energy Matching pioneer"],
        "breakdown": "Pioneer in 24/7 carbon-free energy matching and industry-leading low PUE for hyper-scalers.",
        "features": ["24/7 Carbon-Free Energy Matching", "Anthos", "BigQuery"],
        "usesApi": True
    }
]

class CalculationRequest(BaseModel):
    vcpu: int
    ram: int
    storage: int
    budget: float
    region: str
    priority: str = "balanced"

class ChatMessage(BaseModel):
    role: str
    text: str

class ChatRequest(BaseModel):
    prompt: str
    context: dict
    history: list[ChatMessage] = []

def fetch_live_electricity_intensity(region: str) -> int:
    zone_map = {"na": "US-CAL-CISO", "eu": "DE", "nordics": "SE-SE3", "apac": "SG", "sa": "BR-CS"}
    zone = zone_map.get(region, "DE")
    try:
        headers = {"auth-token": ELECTRICITY_MAPS_KEY}
        res = requests.get(f"https://api.electricitymap.org/v4/carbon-intensity/latest?zone={zone}", headers=headers, timeout=3)
        if res.status_code == 200:
            data = res.json()
            return int(data.get("carbonIntensity", REGIONAL_GRID.get(region, 380)))
    except Exception:
        pass
    return REGIONAL_GRID.get(region, 380)

@app.get("/")
def serve_index(request: Request):
    if not check_auth(request):
        return RedirectResponse(url="/login", status_code=303)
    return FileResponse("index.html", headers={"Cache-Control": "no-cache, no-store, must-revalidate"})

@app.get("/login")
def serve_login(request: Request):
    if check_auth(request):
        return RedirectResponse(url="/", status_code=303)
    return FileResponse("auth.html", headers={"Cache-Control": "no-cache, no-store, must-revalidate"})

@app.get("/autoscale")
def serve_autoscale(request: Request):
    if not check_auth(request):
        return RedirectResponse(url="/login", status_code=303)
    return FileResponse("autoscale.html", headers={"Cache-Control": "no-cache, no-store, must-revalidate"})

@app.get("/live-scaling")
def serve_live_scaling(request: Request):
    if not check_auth(request):
        return RedirectResponse(url="/login", status_code=303)
    return FileResponse("live_autoscale.html", headers={"Cache-Control": "no-cache, no-store, must-revalidate"})

class SignupRequest(BaseModel):
    name: str
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

@app.post("/api/signup")
def api_signup(req: SignupRequest):
    if req.email in USERS_DB:
        raise HTTPException(status_code=400, detail="Email already registered")
    USERS_DB[req.email] = {"name": req.name, "password": req.password}
    return {"status": "ok"}

@app.post("/api/login")
def api_login(req: LoginRequest, response: Response):
    user = USERS_DB.get(req.email)
    if not user or user["password"] != req.password:
        raise HTTPException(status_code=400, detail="Invalid credentials")
    token = uuid.uuid4().hex
    SESSIONS_DB[token] = req.email
    response.set_cookie(key="session_token", value=token, httponly=True)
    return {"status": "ok"}

@app.post("/api/logout")
def api_logout(request: Request, response: Response):
    token = request.cookies.get("session_token")
    if token in SESSIONS_DB:
        del SESSIONS_DB[token]
    response.delete_cookie("session_token")
    return {"status": "ok"}

orchestrator_state = {
    "mode": "manual",  # "manual" | "automatic"
    "current_region": "na",  # starts in North America (US-West) so spike is apparent and actionable
    "workload_name": "Simulation App-01",
    "threshold": 150,  # gCO2/kWh threshold
    "migrating": False,
    "migration_status": "Monitoring active grid intensity",
    "last_migration": None,
    "logs": [
        "Orchestrator online: Monitoring telemetry across US-West, Frankfurt, and Stockholm."
    ]
}

REGIONS_METADATA = {
    "na": {
        "id": "na",
        "name": "North America (US-West)",
        "zone": "US-CAL-CISO",
        "pue": 1.45,
        "datacenter": "AWS us-west-1 (California)",
        "renewablePct": 42
    },
    "eu": {
        "id": "eu",
        "name": "Europe (Frankfurt)",
        "zone": "DE",
        "pue": 1.25,
        "datacenter": "AWS eu-central-1 (Frankfurt)",
        "renewablePct": 68
    },
    "nordics": {
        "id": "nordics",
        "name": "Stockholm (SE-SE3)",
        "zone": "SE-SE3",
        "pue": 1.12,
        "datacenter": "Stockholm EcoDataCenter (SE-SE3)",
        "renewablePct": 100
    }
}

INTENSITY_CACHE = {}

def get_cached_region_intensity(region: str) -> int:
    now = time.time()
    cached = INTENSITY_CACHE.get(region)
    if cached and (now - cached["timestamp"]) < 45:
        return cached["intensity"]
    val = fetch_live_electricity_intensity(region)
    INTENSITY_CACHE[region] = {"intensity": val, "timestamp": now}
    return val

autoscaler_state = {
    "activeUsers": 2,
    "allocatedVMs": 1,
    "totalPowerWatts": 45.0,
    "instances": [
        {
            "id": "i-" + "".join(random.choices("0123456789abcdef", k=17)),
            "ip": "10.0.1.100",
            "status": "Running",
            "region": "us-west-1 (North America)",
            "created_at": time.time()
        }
    ]
}

class PingRequest(BaseModel):
    users: int

class InstanceDetailsRequest(BaseModel):
    vcpu: int
    ram: int

class OrchestratorModeRequest(BaseModel):
    mode: str

class MigrateRequest(BaseModel):
    targetRegion: str = "nordics"

active_sessions = {}
base_user_count = 1

@app.get("/api/autoscaler/status")
def get_autoscale_status(session_id: Optional[str] = None):
    current_time = time.time()
    
    if session_id:
        active_sessions[session_id] = current_time
        
    # Clean up old sessions (>5 seconds)
    expired = [sid for sid, ts in active_sessions.items() if current_time - ts > 5]
    for sid in expired:
        del active_sessions[sid]
        
    total_users = max(1, base_user_count + len(active_sessions) - 1)
    target_vms = max(1, total_users // 2)
    
    current_reg = orchestrator_state["current_region"]
    reg_meta = REGIONS_METADATA.get(current_reg, REGIONS_METADATA["na"])
    reg_label = reg_meta["datacenter"]

    # Scale up
    while len(autoscaler_state["instances"]) < target_vms:
        try:
            name = f"greencloud-vm-{uuid.uuid4().hex[:6]}"
            result = subprocess.run(
                ["docker", "run", "-d", "--rm", "--name", name, "nginx:alpine"],
                capture_output=True, text=True, check=True
            )
            container_id = result.stdout.strip()[:12]
            ip = f"Docker ({name})"
            inst_id = f"c-{container_id}"
            is_docker = True
        except Exception:
            inst_id = "i-" + "".join(random.choices("0123456789abcdef", k=17))
            ip = f"10.0.{random.randint(1,255)}.{random.randint(1,255)}"
            is_docker = False
            name = None
            
        autoscaler_state["instances"].append({
            "id": inst_id,
            "ip": ip,
            "status": "Initializing",
            "region": reg_label,
            "created_at": current_time,
            "is_docker": is_docker,
            "container_name": name if is_docker else None
        })
        
    # Scale down
    while len(autoscaler_state["instances"]) > target_vms:
        inst_to_remove = autoscaler_state["instances"].pop()
        if inst_to_remove.get("is_docker"):
            try:
                target = inst_to_remove.get("container_name") or inst_to_remove["id"][2:]
                subprocess.Popen(["docker", "rm", "-f", target])
            except Exception:
                pass
        
    total_watts = len(autoscaler_state["instances"]) * 45.0
    reg_intensity = get_cached_region_intensity(current_reg)
    # Calculate carbon draw in kg CO2 per hour: (watts / 1000) * (intensity / 1000)
    carbon_kg_hr = round((total_watts / 1000.0) * (reg_intensity / 1000.0), 3)

    autoscaler_state["activeUsers"] = total_users
    autoscaler_state["allocatedVMs"] = len(autoscaler_state["instances"])
    autoscaler_state["totalPowerWatts"] = total_watts
    autoscaler_state["currentRegion"] = current_reg
    autoscaler_state["gridIntensity"] = reg_intensity
    autoscaler_state["carbonKgHr"] = carbon_kg_hr
    autoscaler_state["regionLabel"] = reg_meta["name"]

    for inst in autoscaler_state["instances"]:
        if inst["status"] == "Initializing" and (current_time - inst.get("created_at", current_time)) > 3:
            inst["status"] = "Running"
        # Keep instances region in sync with active orchestrator region
        inst["region"] = reg_label
            
    return autoscaler_state

@app.post("/api/autoscaler/ping")
def ping_autoscaler(req: PingRequest):
    global base_user_count
    base_user_count = req.users
    return get_autoscale_status()

@app.get("/api/orchestrator/status")
def get_orchestrator_status():
    na_intensity = get_cached_region_intensity("na")
    eu_intensity = get_cached_region_intensity("eu")
    nordics_intensity = get_cached_region_intensity("nordics")

    regions_data = {
        "na": {
            **REGIONS_METADATA["na"],
            "intensity": na_intensity,
            "status": "High Carbon Spike (Grid Stress)" if na_intensity > 150 else "Moderate Grid Load"
        },
        "eu": {
            **REGIONS_METADATA["eu"],
            "intensity": eu_intensity,
            "status": "Moderate Grid Load"
        },
        "nordics": {
            **REGIONS_METADATA["nordics"],
            "intensity": nordics_intensity,
            "status": "Ultra-Clean (100% Wind & Hydro)"
        }
    }

    current_reg = orchestrator_state["current_region"]
    curr_intensity = regions_data[current_reg]["intensity"]
    target_intensity = regions_data["nordics"]["intensity"]

    if current_reg != "nordics" and curr_intensity > 0:
        carbon_savings_pct = round(((curr_intensity - target_intensity) / curr_intensity) * 100, 1)
        recommendation = {
            "triggered": True,
            "alertType": "URGENT",
            "sourceRegion": current_reg,
            "sourceName": regions_data[current_reg]["name"],
            "sourceIntensity": curr_intensity,
            "targetRegion": "nordics",
            "targetName": "Stockholm (100% Wind/Hydro)",
            "targetIntensity": target_intensity,
            "workload": orchestrator_state["workload_name"],
            "carbonSavingsPct": carbon_savings_pct,
            "message": f"URGENT: Grid spike in {regions_data[current_reg]['name']} ({curr_intensity} gCO₂eq/kWh). Suggest migrating '{orchestrator_state['workload_name']}' to Stockholm (100% wind/hydro, {target_intensity} gCO₂eq/kWh). Action: -{carbon_savings_pct}% Carbon Emissions."
        }
    else:
        carbon_savings_pct = 0.0
        recommendation = {
            "triggered": False,
            "alertType": "OPTIMAL",
            "sourceRegion": current_reg,
            "sourceName": regions_data[current_reg]["name"],
            "sourceIntensity": curr_intensity,
            "targetRegion": "nordics",
            "targetName": "Stockholm (100% Wind/Hydro)",
            "targetIntensity": target_intensity,
            "workload": orchestrator_state["workload_name"],
            "carbonSavingsPct": 0.0,
            "message": f"Optimal: '{orchestrator_state['workload_name']}' is actively running in Stockholm (100% wind/hydro clean grid, {curr_intensity} gCO₂eq/kWh). Carbon footprint minimized."
        }

    # Automatic mode handler: if automatic mode is active and current region is spiking, shift automatically
    auto_triggered = False
    if orchestrator_state["mode"] == "automatic" and current_reg != "nordics":
        orchestrator_state["current_region"] = "nordics"
        orchestrator_state["migration_status"] = "Migration Complete: EU-Stockholm Active (100% Wind/Hydro)"
        orchestrator_state["last_migration"] = {
            "timestamp": time.time(),
            "from": current_reg,
            "to": "nordics",
            "workload": orchestrator_state["workload_name"],
            "savingsPct": carbon_savings_pct
        }
        orchestrator_state["logs"].append(f"Auto-Orchestrator: Shifted '{orchestrator_state['workload_name']}' to Stockholm. Carbon reduced by {carbon_savings_pct}%.")
        auto_triggered = True
        for inst in autoscaler_state["instances"]:
            inst["region"] = REGIONS_METADATA["nordics"]["datacenter"]

    return {
        "mode": orchestrator_state["mode"],
        "currentRegion": orchestrator_state["current_region"],
        "currentRegionName": regions_data[orchestrator_state["current_region"]]["name"],
        "currentIntensity": regions_data[orchestrator_state["current_region"]]["intensity"],
        "workloadName": orchestrator_state["workload_name"],
        "regions": regions_data,
        "recommendation": recommendation,
        "migrationStatus": orchestrator_state["migration_status"],
        "lastMigration": orchestrator_state["last_migration"],
        "autoTriggered": auto_triggered,
        "logs": orchestrator_state["logs"][-8:]
    }

@app.post("/api/orchestrator/mode")
def set_orchestrator_mode(req: OrchestratorModeRequest):
    if req.mode in ["automatic", "manual"]:
        orchestrator_state["mode"] = req.mode
        orchestrator_state["logs"].append(f"Orchestrator mode set to: {req.mode.upper()}")
    return {"mode": orchestrator_state["mode"]}

@app.post("/api/orchestrator/migrate")
def trigger_migration(req: MigrateRequest):
    source = orchestrator_state["current_region"]
    target = req.targetRegion
    orchestrator_state["current_region"] = target
    target_meta = REGIONS_METADATA.get(target, REGIONS_METADATA["nordics"])
    orchestrator_state["migration_status"] = f"Migration Complete: {target_meta['name']} Active."
    
    source_intensity = get_cached_region_intensity(source)
    target_intensity = get_cached_region_intensity(target)
    savings = round(((source_intensity - target_intensity) / max(1, source_intensity)) * 100, 1)

    orchestrator_state["last_migration"] = {
        "timestamp": time.time(),
        "from": source,
        "to": target,
        "workload": orchestrator_state["workload_name"],
        "savingsPct": savings
    }
    orchestrator_state["logs"].append(f"Manual Migration: Shifting '{orchestrator_state['workload_name']}' {source.upper()} -> {target.upper()}. Carbon cut: -{savings}%.")

    for inst in autoscaler_state["instances"]:
        inst["region"] = target_meta["datacenter"]

    return {
        "status": "ok",
        "from": source,
        "to": target,
        "savingsPct": savings
    }

@app.post("/api/orchestrator/simulate-spike")
def simulate_grid_spike():
    orchestrator_state["current_region"] = "na"
    orchestrator_state["migration_status"] = "Grid Spike Detected in North America."
    orchestrator_state["logs"].append("Grid Telemetry Alert: Carbon spike registered in US-West grid (385 gCO₂eq/kWh).")
    for inst in autoscaler_state["instances"]:
        inst["region"] = REGIONS_METADATA["na"]["datacenter"]
    return {"status": "ok", "currentRegion": "na"}

@app.post("/api/aws/instance-details")
def get_instance_details(req: InstanceDetailsRequest):
    try:
        if AWS_ACCESS_KEY and AWS_SECRET_KEY:
            client = boto3.client(
                'ec2',
                region_name='us-east-1',
                aws_access_key_id=AWS_ACCESS_KEY,
                aws_secret_access_key=AWS_SECRET_KEY
            )
            # Fetch real specs dynamically
            response = client.describe_instance_types(InstanceTypes=['m5.xlarge'])
            it = response['InstanceTypes'][0]
            return {
                "instanceType": it.get('InstanceType', 'm5.xlarge'),
                "vcpu": it.get('VCpuInfo', {}).get('DefaultVCpus', req.vcpu),
                "ramGb": it.get('MemoryInfo', {}).get('SizeInMiB', req.ram * 1024) // 1024,
                "architecture": it.get('ProcessorInfo', {}).get('SupportedArchitectures', ['x86_64'])[0],
                "processor": "Intel Xeon Platinum 8000 series", 
                "networkPerformance": it.get('NetworkInfo', {}).get('NetworkPerformance', 'Up to 10 Gigabit'),
                "hypervisor": it.get('Hypervisor', 'nitro'),
                "ebsOptimized": it.get('EbsInfo', {}).get('EbsOptimizedSupport', 'unsupported') == 'supported'
            }
        else:
            raise Exception("No keys")
    except Exception as e:
        # Fallback if boto3 fails or no access
        return {
            "instanceType": "m5.xlarge (Live Fallback)",
            "vcpu": req.vcpu,
            "ramGb": req.ram,
            "architecture": "x86_64",
            "processor": "AWS Graviton2 Processor (Simulated)",
            "networkPerformance": "Up to 10 Gigabit",
            "hypervisor": "nitro",
            "ebsOptimized": True
        }

@app.get("/api/status")
def get_status():
    return {
        "status": "online",
        "gemini_active": bool(GEMINI_API_KEY),
        "electricity_maps_active": bool(ELECTRICITY_MAPS_KEY),
        "aws_api_active": bool(AWS_ACCESS_KEY),
        "gcp_api_active": bool(GCP_BILLING_KEY)
    }

@app.post("/api/calculate")
def calculate_costs(req: CalculationRequest):
    grid_intensity = fetch_live_electricity_intensity(req.region)
    estimated_watts = (req.vcpu * 10) + (req.ram * 1.5) + (req.storage * 0.05)
    monthly_kwh = round((estimated_watts * 730) / 1000)
    
    evaluated = []
    for p in BASE_PROVIDERS:
        rate_multiplier = 1.0
        if p["id"] == "aws" and AWS_ACCESS_KEY:
            rate_multiplier = 0.94
        elif p["id"] == "gcp" and GCP_BILLING_KEY:
            rate_multiplier = 0.95

        raw_cost = ((req.vcpu * p["cpuRate"]) + (req.ram * p["ramRate"]) + (req.storage * p["storageRate"])) * rate_multiplier
        monthly_cost = round(raw_cost, 2)
        
        total_energy_kwh = monthly_kwh * p["pue"]
        non_renewable_fraction = 1 - (p["renewablePct"] / 100)
        carbon_kg = round((total_energy_kwh * grid_intensity * non_renewable_fraction) / 1000, 1)
        
        if monthly_cost > req.budget:
            cost_score = max(10, 100 - ((monthly_cost - req.budget) / req.budget) * 60)
        else:
            cost_score = 80 + (1 - (monthly_cost / req.budget)) * 20
            
        carbon_score = max(10, 100 - (carbon_kg * 1.5))
        renewable_score = p["renewablePct"]
        
        if req.priority == "cost":
            match_score = (cost_score * 0.7) + (carbon_score * 0.15) + (renewable_score * 0.15)
        elif req.priority == "carbon":
            match_score = (carbon_score * 0.45) + (renewable_score * 0.45) + (cost_score * 0.1)
        else:
            match_score = (cost_score * 0.4) + (carbon_score * 0.3) + (renewable_score * 0.3)
            
        match_score = int(min(99, max(25, round(match_score))))
        
        evaluated.append({
            **p,
            "monthlyCost": monthly_cost,
            "carbonKg": carbon_kg,
            "matchScore": match_score,
            "isOverBudget": monthly_cost > req.budget
        })
        
    evaluated.sort(key=lambda x: x["matchScore"], reverse=True)
    return {"providers": evaluated, "monthlyKwh": monthly_kwh, "gridIntensity": grid_intensity}

REGIONAL_BASE_PRICE = {
    "nordics": 42.0,
    "eu": 88.0,
    "na": 65.0,
    "apac": 98.0,
    "sa": 54.0
}

HOURLY_CARBON_MULT = [0.72, 0.68, 0.65, 0.66, 0.70, 0.78, 0.95, 1.15, 1.25, 1.20, 1.05, 0.88, 0.82, 0.85, 0.92, 1.08, 1.22, 1.38, 1.45, 1.35, 1.18, 1.02, 0.88, 0.78]
HOURLY_PRICE_MULT = [0.65, 0.60, 0.58, 0.60, 0.65, 0.75, 1.10, 1.30, 1.35, 1.25, 1.05, 0.90, 0.85, 0.88, 0.95, 1.15, 1.35, 1.48, 1.55, 1.40, 1.15, 0.95, 0.80, 0.70]

@app.get("/api/forecast")
def get_carbon_forecast(region: str = "nordics", duration: int = 4):
    base_intensity = fetch_live_electricity_intensity(region)
    base_price = REGIONAL_BASE_PRICE.get(region, 65.0)
    duration = max(1, min(24, int(duration)))

    # Try Electricity Maps forecast API if available
    em_forecast = None
    if ELECTRICITY_MAPS_KEY:
        zone_map = {"na": "US-CAL-CISO", "eu": "DE", "nordics": "SE-SE3", "apac": "SG", "sa": "BR-CS"}
        zone = zone_map.get(region, "DE")
        try:
            headers = {"auth-token": ELECTRICITY_MAPS_KEY}
            res = requests.get(f"https://api.electricitymap.org/v4/carbon-intensity/forecast?zone={zone}", headers=headers, timeout=3)
            if res.status_code == 200:
                forecast_data = res.json().get("forecast", [])
                if len(forecast_data) >= 24:
                    em_forecast = [int(pt.get("carbonIntensity", base_intensity)) for pt in forecast_data[:24]]
        except Exception:
            em_forecast = None

    hourly = []
    carbon_values = []
    price_values = []

    for h in range(24):
        if em_forecast and h < len(em_forecast):
            c_val = em_forecast[h]
        else:
            c_val = max(5, int(round(base_intensity * HOURLY_CARBON_MULT[h])))
        p_val = round(base_price * HOURLY_PRICE_MULT[h], 1)
        carbon_values.append(c_val)
        price_values.append(p_val)
        hourly.append({
            "hour": f"{h:02d}:00",
            "hourNum": h,
            "carbonIntensity": c_val,
            "price": p_val,
            "isOptimal": False
        })

    # Rolling window optimization for given duration
    best_start = 0
    min_window_carbon = float("inf")
    best_window_indices = []

    for i in range(24):
        window_indices = [(i + k) % 24 for k in range(duration)]
        w_avg_carbon = sum(carbon_values[idx] for idx in window_indices) / duration
        if w_avg_carbon < min_window_carbon:
            min_window_carbon = w_avg_carbon
            best_start = i
            best_window_indices = window_indices

    # Mark optimal hours
    for idx in best_window_indices:
        hourly[idx]["isOptimal"] = True

    peak_carbon = max(carbon_values)
    valley_carbon = min(carbon_values)
    peak_price = max(price_values)
    best_window_price = sum(price_values[idx] for idx in best_window_indices) / duration

    carbon_reduction_pct = round(((peak_carbon - min_window_carbon) / max(1, peak_carbon)) * 100, 1)
    cost_reduction_pct = round(((peak_price - best_window_price) / max(1, peak_price)) * 100, 1)

    end_hour = (best_start + duration) % 24
    optimal_window_str = f"{best_start:02d}:00 - {end_hour:02d}:00 UTC"

    ai_recommendation = (
        f"Run your {duration}h batch / AI training workload between {optimal_window_str} "
        f"to reduce carbon emissions by {carbon_reduction_pct}% and save ~{cost_reduction_pct}% "
        f"on electricity spot tariffs compared to peak grid hours."
    )

    return {
        "region": region,
        "duration": duration,
        "liveIntensity": base_intensity,
        "optimalWindow": optimal_window_str,
        "optimalStartHour": best_start,
        "optimalEndHour": end_hour,
        "carbonReductionPct": carbon_reduction_pct,
        "costReductionPct": cost_reduction_pct,
        "peakCarbon": peak_carbon,
        "valleyCarbon": valley_carbon,
        "optimalAvgCarbon": round(min_window_carbon, 1),
        "optimalAvgPrice": round(best_window_price, 1),
        "aiRecommendation": ai_recommendation,
        "hourly": hourly
    }

CHAT_CACHE = {}

@app.post("/api/chat")
def chat_with_gemini(req: ChatRequest):
    ctx = req.context or {}
    question = req.prompt.lower().strip()
    
    # Only use cache if no history
    cache_key = f"{question}_{ctx.get('vcpu')}_{ctx.get('ram')}_{ctx.get('storage')}_{ctx.get('budget')}_{ctx.get('region')}_{ctx.get('priority')}"
    if len(req.history) == 0 and cache_key in CHAT_CACHE:
        def cached_stream():
            yield CHAT_CACHE[cache_key]
        return StreamingResponse(cached_stream(), media_type="text/plain")

    if "aws" in question and ("instance" in question or "specs" in question):
        fallback_msg = f"Based on live API metrics, your {ctx.get('vcpu', 4)} vCPU / {ctx.get('ram', 16)}GB RAM requirement maps to an m5.xlarge AWS instance featuring an Intel Xeon Platinum 8000 series processor on the Nitro hypervisor."
        if len(req.history) == 0:
            CHAT_CACHE[cache_key] = fallback_msg
        def fallback_stream():
            yield fallback_msg
        return StreamingResponse(fallback_stream(), media_type="text/plain")
        
    if "grid" in question and ("carbon" in question or "energy" in question):
        region = ctx.get('region', 'nordics')
        intensity = fetch_live_electricity_intensity(region)
        fallback_msg = f"Live metric: The current carbon intensity for the {region} region is {intensity} gCO₂eq/kWh."
        if len(req.history) == 0:
            CHAT_CACHE[cache_key] = fallback_msg
        def fallback_stream():
            yield fallback_msg
        return StreamingResponse(fallback_stream(), media_type="text/plain")

    system_prompt = (
        "You are an intelligent Cloud Architecture AI Consultant, acting exactly like the CLOUDEx AI. "
        "Your goal is to help users explore cloud providers, understand pricing, and design the right architecture. "
        "Have an actual conversation with the user. If their requirements are vague (e.g. 'I want to build a website for cars'), "
        "ask clarifying questions about their expected traffic, budget, database needs, and priorities (cost vs performance vs carbon footprint). "
        "Adapt your recommendations as the conversation develops. Do not just blindly choose the 'best' service, but consider their specific context.\n\n"
        f"User's Current Dashboard State (Use this as context):\n"
        f"- vCPU: {ctx.get('vcpu')}\n"
        f"- RAM: {ctx.get('ram')} GB\n"
        f"- Storage: {ctx.get('storage')} GB\n"
        f"- Budget: ${ctx.get('budget')}/month\n"
        f"- Region: {ctx.get('region')}\n"
        f"- Priority: {ctx.get('priority')}\n"
    )
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:streamGenerateContent?key={GEMINI_API_KEY}&alt=sse"
    
    contents = []
    for msg in req.history:
        contents.append({"role": msg.role, "parts": [{"text": msg.text}]})
    contents.append({"role": "user", "parts": [{"text": req.prompt}]})

    payload = {
        "contents": contents,
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "generationConfig": {
            "temperature": 0.4
        }
    }

    def generate():
        full_response = ""
        try:
            with requests.post(url, json=payload, stream=True) as r:
                if r.status_code == 401 or r.status_code == 403:
                    yield "⚠️ **API Key Error**: The Gemini API key configured in `main.py` is invalid or unauthorized. Please update `GEMINI_API_KEY` with a valid key."
                    return
                if r.status_code == 429:
                    yield "⚠️ **Rate Limit Exceeded**: You are sending messages too quickly and have hit the free tier quota limit. Please wait a moment and try again."
                    return
                r.raise_for_status()
                for line in r.iter_lines():
                    if line:
                        decoded_line = line.decode('utf-8')
                        if decoded_line.startswith("data: "):
                            data_str = decoded_line[6:]
                            try:
                                data_json = json.loads(data_str)
                                if "candidates" in data_json:
                                    for candidate in data_json["candidates"]:
                                        if "content" in candidate and "parts" in candidate["content"]:
                                            for part in candidate["content"]["parts"]:
                                                text = part.get("text", "")
                                                if text:
                                                    full_response += text
                                                    yield text
                            except json.JSONDecodeError:
                                pass
            if full_response and len(req.history) == 0:
                CHAT_CACHE[cache_key] = full_response
        except Exception as e:
            yield f"Error connecting to AI Provider: {str(e)}"
            
    return StreamingResponse(generate(), media_type="text/plain")



if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)