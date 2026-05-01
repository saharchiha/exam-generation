import React, { useState } from 'react';
import { BookOpen, Download, Calendar, FileText, CheckCircle, Loader, GraduationCap, TrendingUp, Clock, Globe, Target, Zap, List } from 'lucide-react';

export default function ExamGenerator() {
  const [formData, setFormData] = useState({
    field: '',
    subject: '',
    language: 'french',
    type: 'controle', // contrôle ou synthèse
    session: 'principale',
    difficulty: 'medium',
    numQuestions: '4', // Par défaut 4 exercices
    themes: '', // Thèmes libres
    lycee: '', // Nom du lycée
    professeur: '' // Nom du professeur
  });

  const [generating, setGenerating] = useState(false);
  const [generated, setGenerated] = useState(false);
  const [examData, setExamData] = useState(null);

  const fields = [
    { value: '', label: 'Sélectionner la section' },
    { value: 'maths', label: 'Mathématiques' },
    { value: 'sciences', label: 'Sciences Expérimentales' },
    { value: 'literature', label: 'Lettres' },
    { value: 'economics', label: 'Économie & Gestion' },
    { value: 'technical', label: 'Technique' }
  ];

  const subjectsByField = {
    maths: [
      { value: 'mathématiques', label: 'Mathématiques' },
      { value: 'physique', label: 'Sciences Physiques' },
      { value: 'sciences', label: 'Sciences de la Vie et de la Terre' },
      { value: 'informatique', label: 'Informatique' },
      { value: 'français', label: 'Français' },
      { value: 'arabe', label: 'Arabe' },
      { value: 'anglais', label: 'Anglais' },
      { value: 'philosophie', label: 'Philosophie' }
    ],
    sciences: [
      { value: 'mathématiques', label: 'Mathématiques' },
      { value: 'physique', label: 'Sciences Physiques' },
      { value: 'sciences', label: 'Sciences de la Vie et de la Terre' },
      { value: 'informatique', label: 'Informatique' },
      { value: 'français', label: 'Français' },
      { value: 'arabe', label: 'Arabe' },
      { value: 'anglais', label: 'Anglais' },
      { value: 'philosophie', label: 'Philosophie' }
    ],
    literature: [
      { value: 'français', label: 'Français' },
      { value: 'arabe', label: 'Arabe' },
      { value: 'anglais', label: 'Anglais' },
      { value: 'philosophie', label: 'Philosophie' },
      { value: 'histoire', label: 'Histoire & Géographie' }
    ],
    economics: [
      { value: 'économie', label: 'Économie' },
      { value: 'gestion', label: 'Gestion' },
      { value: 'mathématiques', label: 'Mathématiques' },
      { value: 'français', label: 'Français' },
      { value: 'arabe', label: 'Arabe' },
      { value: 'anglais', label: 'Anglais' },
      { value: 'philosophie', label: 'Philosophie' },
      { value: 'histoire', label: 'Histoire & Géographie' }
    ],
    technical: [
      { value: 'technologie', label: 'Technologie' },
      { value: 'mathématiques', label: 'Mathématiques' },
      { value: 'physique', label: 'Sciences Physiques' },
      { value: 'français', label: 'Français' },
      { value: 'arabe', label: 'Arabe' },
      { value: 'anglais', label: 'Anglais' },
      { value: 'philosophie', label: 'Philosophie' }
    ]
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    if (name === 'field') {
      setFormData({ ...formData, field: value, subject: '' });
    } else {
      setFormData({ ...formData, [name]: value });
    }
    setGenerated(false);
  };

  const handleGenerate = async () => {
    if (!formData.subject || !formData.field) return;
    setGenerating(true);
    try {
      const response = await fetch('http://localhost:8000/api/generate-exam', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          field: formData.field,
          subject: formData.subject,
          language: formData.language,
          type: formData.type, // contrôle ou synthèse
          session: formData.session,
          difficulty: formData.difficulty,
          num_questions: parseInt(formData.numQuestions),
          themes: formData.themes, // thèmes libres
          lycee: formData.lycee, // nom du lycée
          professeur: formData.professeur // nom du professeur
        })
      });
      const data = await response.json();
      if (response.ok) {
        setExamData(data);
        setGenerated(true);
      } else {
        alert('Erreur lors de la génération: ' + (data.detail || data.error));
      }
    } catch (error) {
      alert('Impossible de se connecter au serveur.');
      console.error('Erreur:', error);
    } finally {
      setGenerating(false);
    }
  };

  const handleDownload = async () => {
    if (!examData || !examData.exam_id) {
      alert('Aucun examen disponible');
      return;
    }
    try {
      const response = await fetch(`http://localhost:8000/api/download-exam/${examData.exam_id}`);
      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `devoir_${formData.type}_${examData.exam_id}.pdf`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      } else {
        alert('Échec du téléchargement du PDF');
      }
    } catch (error) {
      alert('Échec du téléchargement.');
      console.error('Erreur:', error);
    }
  };

  const styles = {
    container: {
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
    },
    header: {
      background: 'rgba(255, 255, 255, 0.15)',
      backdropFilter: 'blur(10px)',
      borderBottom: '1px solid rgba(255, 255, 255, 0.2)',
      padding: '24px 20px',
      boxShadow: '0 8px 32px rgba(0, 0, 0, 0.1)'
    },
    headerContent: {
      maxWidth: '900px',
      margin: '0 auto',
      display: 'flex',
      alignItems: 'center',
      gap: '16px'
    },
    logoIcon: {
      background: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
      padding: '14px',
      borderRadius: '16px',
      boxShadow: '0 8px 16px rgba(245, 87, 108, 0.4)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center'
    },
    title: {
      fontSize: '28px',
      fontWeight: '800',
      color: 'white',
      margin: 0,
      textShadow: '2px 2px 4px rgba(0,0,0,0.2)'
    },
    subtitle: {
      fontSize: '14px',
      color: 'rgba(255, 255, 255, 0.95)',
      margin: '4px 0 0 0',
      fontWeight: '600'
    },
    main: {
      maxWidth: '900px',
      margin: '0 auto',
      padding: '60px 20px'
    },
    hero: {
      textAlign: 'center',
      marginBottom: '50px'
    },
    heroTitle: {
      fontSize: '48px',
      fontWeight: '900',
      color: 'white',
      margin: '0 0 16px 0',
      lineHeight: '1.2',
      textShadow: '3px 3px 6px rgba(0,0,0,0.3)'
    },
    heroSubtitle: {
      fontSize: '20px',
      color: 'rgba(255, 255, 255, 0.95)',
      fontWeight: '600',
      textShadow: '1px 1px 2px rgba(0,0,0,0.2)',
      maxWidth: '600px',
      margin: '0 auto'
    },
    card: {
      background: 'rgba(255, 255, 255, 0.98)',
      borderRadius: '24px',
      boxShadow: '0 20px 60px rgba(0, 0, 0, 0.2)',
      overflow: 'hidden',
      border: '4px solid rgba(255, 255, 255, 0.5)'
    },
    cardHeader: {
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      padding: '30px',
      color: 'white'
    },
    cardTitle: {
      fontSize: '24px',
      fontWeight: '800',
      margin: '0 0 8px 0',
      display: 'flex',
      alignItems: 'center',
      gap: '12px'
    },
    cardSubtitle: {
      fontSize: '15px',
      opacity: 0.95,
      fontWeight: '600',
      margin: 0
    },
    cardBody: {
      padding: '40px'
    },
    formGroup: {
      marginBottom: '24px'
    },
    label: {
      display: 'flex',
      alignItems: 'center',
      gap: '10px',
      fontSize: '15px',
      fontWeight: '700',
      color: '#1a202c',
      marginBottom: '10px'
    },
    iconBox: {
      width: '32px',
      height: '32px',
      borderRadius: '10px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center'
    },
    input: {
      width: '100%',
      padding: '16px',
      fontSize: '16px',
      fontWeight: '600',
      border: '3px solid',
      borderRadius: '14px',
      outline: 'none',
      transition: 'all 0.3s',
      boxShadow: '0 4px 12px rgba(0, 0, 0, 0.08)'
    },
    textarea: {
      width: '100%',
      padding: '16px',
      fontSize: '15px',
      fontWeight: '500',
      border: '3px solid',
      borderRadius: '14px',
      outline: 'none',
      transition: 'all 0.3s',
      boxShadow: '0 4px 12px rgba(0, 0, 0, 0.08)',
      minHeight: '100px',
      resize: 'vertical',
      fontFamily: 'inherit'
    },
    button: {
      width: '100%',
      padding: '20px',
      fontSize: '18px',
      fontWeight: '800',
      color: 'white',
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      border: '4px solid rgba(255, 255, 255, 0.3)',
      borderRadius: '14px',
      cursor: 'pointer',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      gap: '12px',
      boxShadow: '0 12px 32px rgba(102, 126, 234, 0.4)',
      transition: 'all 0.3s'
    },
    successCard: {
      background: 'linear-gradient(135deg, #11998e 0%, #38ef7d 100%)',
      borderRadius: '24px',
      padding: '50px',
      textAlign: 'center',
      boxShadow: '0 20px 60px rgba(56, 239, 125, 0.4)',
      border: '4px solid rgba(255, 255, 255, 0.5)',
      marginTop: '40px'
    },
    successIcon: {
      width: '80px',
      height: '80px',
      background: 'white',
      borderRadius: '50%',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      margin: '0 auto 24px',
      boxShadow: '0 8px 24px rgba(0, 0, 0, 0.2)'
    },
    successTitle: {
      fontSize: '36px',
      fontWeight: '900',
      color: 'white',
      marginBottom: '12px'
    },
    successText: {
      fontSize: '18px',
      color: 'white',
      fontWeight: '600',
      marginBottom: '30px'
    },
    downloadButton: {
      padding: '20px 40px',
      fontSize: '18px',
      fontWeight: '800',
      background: 'white',
      color: '#11998e',
      border: '4px solid rgba(17, 153, 142, 0.3)',
      borderRadius: '14px',
      cursor: 'pointer',
      display: 'inline-flex',
      alignItems: 'center',
      gap: '12px',
      boxShadow: '0 12px 32px rgba(0, 0, 0, 0.2)',
      transition: 'all 0.3s'
    },
    hint: {
      fontSize: '13px',
      color: '#6b7280',
      fontWeight: '600',
      marginTop: '8px',
      fontStyle: 'italic'
    }
  };

  const inputColors = {
    field: { bg: 'linear-gradient(135deg, #e0f2fe 0%, #dbeafe 100%)', border: '#3b82f6' },
    subject: { bg: 'linear-gradient(135deg, #dcfce7 0%, #d1fae5 100%)', border: '#10b981' },
    language: { bg: 'linear-gradient(135deg, #fae8ff 0%, #f3e8ff 100%)', border: '#a855f7' },
    type: { bg: 'linear-gradient(135deg, #fed7aa 0%, #fef3c7 100%)', border: '#f59e0b' },
    session: { bg: 'linear-gradient(135deg, #cffafe 0%, #e0f2fe 100%)', border: '#06b6d4' },
    difficulty: { bg: 'linear-gradient(135deg, #fecaca 0%, #fee2e2 100%)', border: '#ef4444' },
    questions: { bg: 'linear-gradient(135deg, #fef3c7 0%, #fed7aa 100%)', border: '#f59e0b' },
    themes: { bg: 'linear-gradient(135deg, #e9d5ff 0%, #f3e8ff 100%)', border: '#9333ea' }
  };

  // Supprimer la fonction getDuration qui n'est plus nécessaire

  return (
    <div style={styles.container}>
      <header style={styles.header}>
        <div style={styles.headerContent}>
          <div style={styles.logoIcon}>
            <GraduationCap size={32} color="white" />
          </div>
          <div>
            <h1 style={styles.title}>Générateur de Devoirs - Baccalauréat Tunisien</h1>
            <p style={styles.subtitle}>Plateforme Professionnelle pour Enseignants</p>
          </div>
        </div>
      </header>

      <main style={styles.main}>
        <div style={styles.hero}>
          <h2 style={styles.heroTitle}>
            Générez Votre<br />
            Devoir en Minutes
          </h2>
          <p style={styles.heroSubtitle}>
            Créez des devoirs de contrôle ou de synthèse adaptés au programme tunisien
          </p>
        </div>

        <div style={styles.card}>
          <div style={styles.cardHeader}>
            <h3 style={styles.cardTitle}>
              <Target size={24} />
              Configuration du Devoir
            </h3>
            <p style={styles.cardSubtitle}>Personnalisez les paramètres de votre devoir</p>
          </div>

          <div style={styles.cardBody}>
            {/* Champs Lycée et Professeur */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
              <div style={styles.formGroup}>
                <label style={styles.label}>
                  <div style={{ ...styles.iconBox, background: 'linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%)' }}>
                    <GraduationCap size={18} color="white" />
                  </div>
                  Nom du Lycée
                </label>
                <input
                  type="text"
                  name="lycee"
                  value={formData.lycee}
                  onChange={handleChange}
                  placeholder="Ex: Lycée Bourguiba"
                  style={{ ...styles.input, background: 'linear-gradient(135deg, #ede9fe 0%, #ddd6fe 100%)', borderColor: '#8b5cf6' }}
                />
              </div>

              <div style={styles.formGroup}>
                <label style={styles.label}>
                  <div style={{ ...styles.iconBox, background: 'linear-gradient(135deg, #ec4899 0%, #db2777 100%)' }}>
                    <BookOpen size={18} color="white" />
                  </div>
                  Nom du Professeur
                </label>
                <input
                  type="text"
                  name="professeur"
                  value={formData.professeur}
                  onChange={handleChange}
                  placeholder="Ex: M. Benali"
                  style={{ ...styles.input, background: 'linear-gradient(135deg, #fce7f3 0%, #fbcfe8 100%)', borderColor: '#ec4899' }}
                />
              </div>
            </div>

            <div style={styles.formGroup}>
              <label style={styles.label}>
                <div style={{ ...styles.iconBox, background: 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)' }}>
                  <GraduationCap size={18} color="white" />
                </div>
                Section
              </label>
              <select
                name="field"
                value={formData.field}
                onChange={handleChange}
                style={{ ...styles.input, background: inputColors.field.bg, borderColor: inputColors.field.border }}
              >
                {fields.map(f => <option key={f.value} value={f.value}>{f.label}</option>)}
              </select>
            </div>

            {formData.field && (
              <div style={styles.formGroup}>
                <label style={styles.label}>
                  <div style={{ ...styles.iconBox, background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)' }}>
                    <BookOpen size={18} color="white" />
                  </div>
                  Matière
                </label>
                <select
                  name="subject"
                  value={formData.subject}
                  onChange={handleChange}
                  style={{ ...styles.input, background: inputColors.subject.bg, borderColor: inputColors.subject.border }}
                >
                  <option value="">Sélectionner une matière</option>
                  {subjectsByField[formData.field]?.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
                </select>
              </div>
            )}

            <div style={styles.formGroup}>
              <label style={styles.label}>
                <div style={{ ...styles.iconBox, background: 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)' }}>
                  <FileText size={18} color="white" />
                </div>
                Type de Devoir
              </label>
              <select
                name="type"
                value={formData.type}
                onChange={handleChange}
                style={{ ...styles.input, background: inputColors.type.bg, borderColor: inputColors.type.border }}
              >
                <option value="controle">📝 Devoir de Contrôle</option>
                <option value="synthese">📚 Devoir de Synthèse</option>
              </select>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
              <div style={styles.formGroup}>
                <label style={styles.label}>
                  <div style={{ ...styles.iconBox, background: 'linear-gradient(135deg, #a855f7 0%, #9333ea 100%)' }}>
                    <Globe size={18} color="white" />
                  </div>
                  Langue
                </label>
                <select
                  name="language"
                  value={formData.language}
                  onChange={handleChange}
                  style={{ ...styles.input, background: inputColors.language.bg, borderColor: inputColors.language.border }}
                >
                  <option value="french">🇫🇷 Français</option>
                  <option value="arabic">🇹🇳 Arabe</option>
                  <option value="english">🇬🇧 Anglais</option>
                </select>
              </div>

              <div style={styles.formGroup}>
                <label style={styles.label}>
                  <div style={{ ...styles.iconBox, background: 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)' }}>
                    <TrendingUp size={18} color="white" />
                  </div>
                  Difficulté
                </label>
                <select
                  name="difficulty"
                  value={formData.difficulty}
                  onChange={handleChange}
                  style={{ ...styles.input, background: inputColors.difficulty.bg, borderColor: inputColors.difficulty.border }}
                >
                  <option value="easy">Facile</option>
                  <option value="medium">Moyen</option>
                  <option value="hard">Difficile</option>
                </select>
              </div>
            </div>

            <div style={styles.formGroup}>
              <label style={styles.label}>
                <div style={{ ...styles.iconBox, background: 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)' }}>
                  <FileText size={18} color="white" />
                </div>
                Nombre d'Exercices
              </label>
              <input
                type="number"
                name="numQuestions"
                value={formData.numQuestions}
                onChange={handleChange}
                min="3"
                max="5"
                style={{ ...styles.input, background: inputColors.questions.bg, borderColor: inputColors.questions.border }}
              />
              <p style={styles.hint}>
                Entre 3 et 5 exercices (recommandé: 4 exercices de 5 points)
              </p>
            </div>

            <div style={styles.formGroup}>
              <label style={styles.label}>
                <div style={{ ...styles.iconBox, background: 'linear-gradient(135deg, #9333ea 0%, #7e22ce 100%)' }}>
                  <List size={18} color="white" />
                </div>
                Thèmes / Chapitres à Aborder
              </label>
              <textarea
                name="themes"
                value={formData.themes}
                onChange={handleChange}
                placeholder="Exemple: Dérivées, Limites, Continuité, Étude de fonctions..."
                style={{ ...styles.textarea, background: inputColors.themes.bg, borderColor: inputColors.themes.border }}
              />
              <p style={styles.hint}>
                Spécifiez les chapitres ou thèmes que vous souhaitez inclure (optionnel, séparés par des virgules)
              </p>
            </div>

            <button
              onClick={handleGenerate}
              disabled={generating || !formData.subject || !formData.field}
              style={{
                ...styles.button,
                opacity: (generating || !formData.subject || !formData.field) ? 0.5 : 1,
                cursor: (generating || !formData.subject || !formData.field) ? 'not-allowed' : 'pointer'
              }}
              onMouseEnter={(e) => !generating && formData.subject && formData.field && (e.target.style.transform = 'scale(1.02)')}
              onMouseLeave={(e) => (e.target.style.transform = 'scale(1)')}
            >
              {generating ? (
                <>
                  <Loader size={24} className="spin" />
                  Génération en cours...
                </>
              ) : (
                <>
                  <Zap size={24} />
                  Générer le Devoir
                </>
              )}
            </button>
          </div>
        </div>

        {generated && (
          <div style={styles.successCard}>
            <div style={styles.successIcon}>
              <CheckCircle size={48} color="#11998e" />
            </div>
            <h3 style={styles.successTitle}>Devoir Généré avec Succès !</h3>
            <p style={styles.successText}>
              Votre devoir de {formData.type} est prêt à être téléchargé
            </p>
            <button
              onClick={handleDownload}
              style={styles.downloadButton}
              onMouseEnter={(e) => (e.target.style.transform = 'scale(1.05)')}
              onMouseLeave={(e) => (e.target.style.transform = 'scale(1)')}
            >
              <Download size={24} />
              Télécharger le PDF
            </button>
          </div>
        )}
      </main>

      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        .spin {
          animation: spin 1s linear infinite;
        }
        @media (max-width: 768px) {
          div[style*="grid-template-columns: 1fr 1fr"] {
            grid-template-columns: 1fr !important;
          }
        }
      `}</style>
    </div>
  );
}