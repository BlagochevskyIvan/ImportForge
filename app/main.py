from fastapi import FastAPI

app = FastAPI()

@app.post("/suppliers")
async def create_supplier(supplier: dict):
    pass

@app.get("/suppliers")
async def get_suppliers():
    pass

@app.post("/suppliers/{id}/config")
async def create_supplier_config(id: int, config: dict):
    pass

@app.get("/suppliers/{id}/config")
async def get_supplier_config(id: int):
    pass