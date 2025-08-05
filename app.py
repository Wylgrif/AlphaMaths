import streamlit as st
import openai
import subprocess
import os
from pathlib import Path
import tempfile

# --- Configuration de la page Streamlit ---
st.set_page_config(page_title="AlphaEvolve Math Proof Validator", layout="wide")

st.title("AlphaEvolve Math Proof Validator")
st.markdown("Cet outil génère et valide des démonstrations mathématiques en utilisant une IA et Lean.")

# --- Fonction de validation Lean (adaptée du fichier fourni) ---
def verify_lean_file(file_path: str) -> tuple[bool, str]:
    """
    Vérifie si un fichier Lean est syntaxiquement correct et que les preuves sont valides.

    Args:
        file_path: Chemin vers le fichier .lean

    Returns:
        tuple[bool, str]: (True si la vérification réussit, False sinon, et la sortie/erreur de Lean)
    """
    try:
        if not Path(file_path).exists():
            return False, f"Erreur: Le fichier {file_path} n'existe pas."

        # Exécute Lean en ligne de commande
        # Utilisation de 'lean --run' pour s'assurer que le fichier est compilé et exécuté si nécessaire
        # et que toutes les erreurs de preuve sont capturées.
        result = subprocess.run(
            ["lean", "--run", file_path],
            capture_output=True,
            text=True,
            check=True,
            encoding='utf-8' # Spécifier l'encodage pour éviter les erreurs sur certains systèmes
        )

        return True, "✅ La preuve dans le fichier Lean est valide!\n" + result.stdout

    except FileNotFoundError:
        return False, "❌ Erreur: La commande 'lean' n'a pas été trouvée. Assurez-vous que Lean est installé et dans votre PATH."
    except subprocess.CalledProcessError as e:
        return False, "❌ La preuve contient des erreurs!\n" + e.stderr
    except Exception as e:
        return False, f"Erreur inattendue lors de la vérification Lean: {str(e)}"

# --- Interface utilisateur Streamlit ---

# Sidebar pour les configurations de l'IA
st.sidebar.header("Configuration de l'IA")
openai_api_base = st.sidebar.text_input("URL de l'API", value="http://localhost:11434/v1/")
openai_api_key = st.sidebar.text_input("Clé API (si requise)", type="password", help="Non requise pour les modèles locaux comme Ollama.")
openai_model = st.sidebar.text_input(
    "Modèle",
    value="mistral-small3.2:latest", # Valeur par défaut
    help="Entrez le nom du modèle à utiliser pour la génération de démonstrations (ex: gpt-4o, mistral-small3.2:latest, etc.)."
)

# Zone d'entrée principale
st.header("Problème Mathématique / Conjecture")
math_problem_input = st.text_area(
    "Décrivez le problème mathématique ou la conjecture à prouver (en français ou en anglais). "
    "Soyez aussi précis que possible pour aider l'IA à générer une démonstration pertinente.",
    height=200,
    placeholder="Ex: Démontrer que pour tout entier n > 2, il n'existe pas d'entiers positifs a, b, c tels que a^n + b^n = c^n (Théorème de Fermat)."
)

if st.button("Lancer le processus de validation"):
    if not math_problem_input:
        st.error("Veuillez décrire le problème mathématique.")
    else:
        st.info("Processus lancé... Génération de la démonstration par l'IA.")
        # Pour Ollama ou les API locales, une clé n'est souvent pas nécessaire,
        # mais la bibliothèque peut en exiger une. On utilise une valeur factice si aucune n'est fournie.
        openai.api_key = openai_api_key if openai_api_key else "ollama"
        openai.api_base = openai_api_base

        max_attempts = 3  # Nombre maximal de tentatives de génération/validation
        attempt = 0
        lean_error_feedback = ""
        generated_proof_code = ""
        is_valid = False
        lean_output = ""

        while attempt < max_attempts and not is_valid:
            attempt += 1
            st.subheader(f"Tentative {attempt}/{max_attempts}")

            try:
                # --- Étape 1: Génération de la démonstration par l'IA ---
                prompt = (
                    f"Vous êtes un assistant de preuve mathématique. "
                    f"Générez une démonstration formelle en langage Lean 4 pour la conjecture/problème suivant :\n\n"
                    f"{math_problem_input}\n\n"
                    f"La démonstration doit être complète et valide syntaxiquement en Lean 4. "
                    f"Incluez les imports nécessaires et utilisez des tactiques appropriées. "
                    f"Ne générez que le code Lean, sans explication supplémentaire.\n\n"
                )

                if lean_error_feedback:
                    prompt += f"Les tentatives précédentes ont échoué avec les erreurs Lean suivantes :\n```\n{lean_error_feedback}\n```\n" \
                              f"Veuillez corriger ces erreurs et fournir une démonstration valide."

                with st.spinner(f"Génération de la démonstration par l'IA (Tentative {attempt})..."):
                    response = openai.chat.completions.create(
                        model=openai_model,
                        messages=[
                            {"role": "system", "content": "You are a helpful assistant that generates Lean 4 code."},
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0.7,
                        max_tokens=2000,
                    )
                
                generated_proof_code = response.choices[0].message.content
                
                if "```lean" in generated_proof_code and "```" in generated_proof_code:
                    # Extraire le code entre les balises ```lean et ```
                    start_index = generated_proof_code.find("```lean") + len("```lean")
                    end_index = generated_proof_code.find("```", start_index)
                    if start_index != -1 and end_index != -1:
                        generated_proof_code = generated_proof_code[start_index:end_index].strip()
                    else:
                        st.warning("Le code Lean généré ne semble pas être correctement formaté avec des balises ```lean et ```. Tentative d'utilisation du texte brut.")
                
                st.subheader("Démonstration Générée par l'IA (Lean 4)")
                st.code(generated_proof_code, language="lean")

                # --- Étape 2: Sauvegarde temporaire et validation par Lean ---
                with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".lean", encoding='utf-8') as temp_lean_file:
                    temp_lean_file.write(generated_proof_code)
                    temp_file_path = temp_lean_file.name

                st.info(f"Validation de la démonstration avec Lean... (Fichier temporaire: {temp_file_path})")
                with st.spinner("Validation en cours par Lean..."):
                    is_valid, lean_output = verify_lean_file(temp_file_path)

                st.subheader("Résultat de la Validation Lean")
                if is_valid:
                    st.success("La démonstration est valide selon Lean!")
                else:
                    st.error("La démonstration contient des erreurs selon Lean!")
                    lean_error_feedback = lean_output # Capture feedback for next attempt
                st.code(lean_output, language="bash")

                # --- Nettoyage du fichier temporaire ---
                os.remove(temp_file_path)
                st.success("Processus terminé. Fichier temporaire nettoyé.")

            except openai.APIError as e:
                st.error(f"Erreur de l'API: {e}")
                st.error("Vérifiez votre clé API et l'URL de l'API.")
                break # Exit loop on API error
            except Exception as e:
                st.error(f"Une erreur inattendue est survenue: {e}")
                st.warning("Assurez-vous que Lean est installé et accessible via la commande 'lean' dans votre terminal.")
                break # Exit loop on unexpected error

        if is_valid:
            st.success("La démonstration finale est valide!")
        else:
            st.error("Impossible de générer une démonstration valide après plusieurs tentatives.")
            st.warning("Veuillez revoir le problème mathématique ou les configurations de l'IA.")

st.markdown("---")
st.markdown("Pour exécuter cette application: `streamlit run app.py` dans votre terminal.")
st.markdown("Assurez-vous d'avoir Lean 4 installé et configuré dans votre PATH.")
