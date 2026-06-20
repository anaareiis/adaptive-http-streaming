import os
import subprocess
import sys
from graphs import generate_comparison_graphs

def find_dynamic_csv(directory):
    """Procura por qualquer arquivo CSV que comece com 'metrics_' no diretório."""
    if not os.path.exists(directory):
        return None
    for file in os.listdir(directory):
        if file.startswith("metrics") and file.endswith(".csv"):
            return os.path.join(directory, file)
    return None

def run():
    # Caminhos base absolutos ajustados para bater com a sua estrutura de pastas
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(base_dir)

    log_dir_rate = os.path.join(project_root, "logs", "rate_based")
    log_dir_buffer = os.path.join(project_root, "logs", "buffer_based")
    
    # Pasta de gráficos comparativos: logs/graphs/
    comparison_graphs_dir = os.path.join(project_root, "logs", "graphs")
    
    main_script = os.path.join(base_dir, "main.py")
    segments = 20  
    manifest_url = "http://137.131.178.229:8080/manifest"

    print("=== Iniciando Rodada 1: Rate-Based ===")
    subprocess.run([
        sys.executable, main_script,
        "--policy", "rate-based",
        "--segments", str(segments),
        "--output-dir", log_dir_rate,
        "--manifest", manifest_url
    ], check=True)

    print("\n=== Iniciando Rodada 2: Buffer-Based ===")
    subprocess.run([
        sys.executable, main_script,
        "--policy", "buffer-based",
        "--segments", str(segments),
        "--output-dir", log_dir_buffer,
        "--manifest", manifest_url
    ], check=True)

    # Localização dinâmica dos CSVs com timestamp (ex: metrics_202606...)
    csv_rate = find_dynamic_csv(log_dir_rate)
    csv_buffer = find_dynamic_csv(log_dir_buffer)
    
    # Validação de segurança
    if not csv_rate:
        raise FileNotFoundError(f"Nenhum CSV de métricas encontrado em: {log_dir_rate}")
    if not csv_buffer:
        raise FileNotFoundError(f"Nenhum CSV de métricas encontrado em: {log_dir_buffer}")

    print(f"\n[ok] Arquivos dinâmicos localizados:")
    print(f" -> Rate-Based CSV: {os.path.basename(csv_rate)}")
    print(f" -> Buffer-Based CSV: {os.path.basename(csv_buffer)}")

    # Garante que a pasta logs/graphs exista antes de gerar os comparativos
    os.makedirs(comparison_graphs_dir, exist_ok=True)

    print("\n=== Gerando Gráficos Comparativos Sobrepostos (Issue 15) ===")
    generate_comparison_graphs(
        csv1=csv_rate,
        csv2=csv_buffer,
        labels=["Rate-Based", "Buffer-Based"],
        output_dir=comparison_graphs_dir
    )
    print(f"✨ Sucesso! Os gráficos comparativos foram salvos em: {comparison_graphs_dir}")

if __name__ == "__main__":
    run()