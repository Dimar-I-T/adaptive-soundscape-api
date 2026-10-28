## Installation

### 1. Cloning and enter the folder
```bash
git clone https://github.com/Dimar-I-T/adaptive-soundscape-api
cd adaptive-soundscape-api
```

### 2. Install Dependencies
Install UV first if you don't have it yet
<br>Windows:
```bash
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Sync to the dependencies
```bash
python -m venv venv
```

```bash
venv\Scripts\activate
```

```bash
pip install -r requirements.txt
```

```bash
uv sync
```

### 3. Configure env (not from here ofc)

### 4. Run App
```bash
fastapi dev main.py  
```