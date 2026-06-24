import os
import subprocess
import sys
from graphs import generate_comparison_graphs

def find_dynamic_csv(directory):
    if not os.path.exists(directory):
        return None
    for file in os.listdir(directory):
        if file.startswith("metrics") and file.endswith(".csv"):
            return os.path.join(directory, file)
    return None

def run():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(base_dir)

    # Criação dos subdiretórios para isolar os logs de cada execução
    log_dir_rate = os.path.join(project_root, "logs", "rate_based")
    log_dir_buffer = os.path.join(project_root, "logs", "buffer_based")
    log_dir_hybrid = os.path.join(project_root, "logs", "hybrid")
    comparison_graphs_dir = os.path.join(project_root, "graphs", "comparison")
    
    main_script = os.path.join(base_dir, "main.py")
    segments = 20  
    manifest_url = "http://137.131.178.229:8080/manifest"

    # Rodada 1
    print("=== Iniciando Rodada 1: Rate-Based ===")
    subprocess.run([
        sys.executable, main_script,
        "--policy", "rate-based",
        "--segments", str(segments),
        "--output-dir", log_dir_rate,
        "--manifest", manifest_url
    ], check=True)

    # Rodada 2
    print("\n=== Iniciando Rodada 2: Buffer-Based ===")
    subprocess.run([
        sys.executable, main_script,
        "--policy", "buffer-based",
        "--segments", str(segments),
        "--output-dir", log_dir_buffer,
        "--manifest", manifest_url
    ], check=True)

    # Rodada 3 (Implementando a chamada da Política 3 criada na Issue 16)
    print("\n=== Iniciando Rodada 3: Hybrid (Política 3) ===")
    subprocess.run([
        sys.executable, main_script,
        "--policy", "hybrid",
        "--segments", str(segments),
        "--output-dir", log_dir_hybrid,
        "--manifest", manifest_url
    ], check=True)

    # Coleta dinâmica dos arquivos CSV gerados
    csv_rate = find_dynamic_csv(log_dir_rate)
    csv_buffer = find_dynamic_csv(log_dir_buffer)
    csv_hybrid = find_dynamic_csv(log_dir_hybrid)
    
    if not all([csv_rate, csv_buffer, csv_hybrid]):
        raise FileNotFoundError("Erro ao localizar um ou mais arquivos CSV gerados na simulação.")

    print(f"\n[ok] Todos os arquivos foram localizados com sucesso.")

    # Execução do gerador estendido passando as 3 listas emparelhadas
    print("\n=== Gerando Gráficos Comparativos Triplos Sobrepostos ===")
    csv_list = [csv_rate, csv_buffer, csv_hybrid]
    label_list = ["Rate-Based", "Buffer-Based", "Hybrid (P3)"]
    
    generate_comparison_graphs(
        csv_paths=csv_list,
        labels=label_list,
        output_dir=comparison_graphs_dir
    )

if __name__ == "__main__":
    run()