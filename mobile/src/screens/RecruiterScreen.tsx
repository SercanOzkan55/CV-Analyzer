import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, Alert, FlatList,
  TouchableOpacity, TextInput, Modal, ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import * as DocumentPicker from 'expo-document-picker';
import { useAuth } from '../contexts/AuthContext';
import {
  recruiterListJobs, recruiterCreateJob, recruiterBatchRank,
  recruiterDashboardAction, recruiterDashboardActions,
  recruiterListTemplates, recruiterCreateTemplate, recruiterDeleteTemplate,
  recruiterSendEmail,
} from '../api/client';
import Card from '../components/Card';
import Button from '../components/Button';
import ScoreCircle from '../components/ScoreCircle';
import SkillTags from '../components/SkillTags';
import { Colors, Spacing, FontSize, BorderRadius, getScoreColor } from '../theme';

type Tab = 'rank' | 'decisions' | 'templates';

export default function RecruiterScreen({ navigation }: any) {
  const { token, user } = useAuth();
  const c = Colors.light;

  const [tab, setTab] = useState<Tab>('rank');
  const [jobs, setJobs] = useState<any[]>([]);
  const [selectedJob, setSelectedJob] = useState<any>(null);

  // Rank tab
  const [jdText, setJdText] = useState('');
  const [cvFiles, setCvFiles] = useState<any[]>([]);
  const [ranked, setRanked] = useState<any[]>([]);
  const [rankLoading, setRankLoading] = useState(false);
  const [candidateActions, setCandidateActions] = useState<Record<string, string>>({});

  // Decisions tab
  const [actions, setActions] = useState<any[]>([]);
  const [actionsLoading, setActionsLoading] = useState(false);

  // Templates tab
  const [templates, setTemplates] = useState<any[]>([]);
  const [tplLoading, setTplLoading] = useState(false);
  const [tplForm, setTplForm] = useState({ name: '', template_type: 'accept', subject: '', body: '' });

  // Modals
  const [jobModal, setJobModal] = useState(false);
  const [jobForm, setJobForm] = useState({ title: '', description: '' });
  const [emailModal, setEmailModal] = useState(false);
  const [emailTarget, setEmailTarget] = useState<any>(null);
  const [emailTplId, setEmailTplId] = useState('');
  const [emailAddr, setEmailAddr] = useState('');
  const [emailSending, setEmailSending] = useState(false);
  const [senderEmail, setSenderEmail] = useState('');

  // Load jobs
  const loadJobs = useCallback(async () => {
    if (!token) return;
    try {
      const data = await recruiterListJobs(token);
      const list = Array.isArray(data) ? data : data?.jobs || [];
      setJobs(list);
      if (!selectedJob && list.length > 0) setSelectedJob(list[0]);
    } catch { /* ignore */ }
  }, [token]);

  useEffect(() => { loadJobs(); }, [loadJobs]);

  // Load actions
  useEffect(() => {
    if (tab !== 'decisions' || !selectedJob?.id || !token) return;
    setActionsLoading(true);
    recruiterDashboardActions(token, selectedJob.id)
      .then(data => setActions(Array.isArray(data) ? data : data?.actions || []))
      .catch(() => setActions([]))
      .finally(() => setActionsLoading(false));
  }, [tab, selectedJob, token]);

  // Load templates
  useEffect(() => {
    if (tab !== 'templates' || !token) return;
    setTplLoading(true);
    recruiterListTemplates(token)
      .then(data => setTemplates(Array.isArray(data) ? data : data?.templates || []))
      .catch(() => setTemplates([]))
      .finally(() => setTplLoading(false));
  }, [tab, token]);

  // ── Handlers ──────────────────────────────────────────────

  async function handleCreateJob() {
    if (!jobForm.title.trim() || !token) return;
    try {
      await recruiterCreateJob(token, jobForm);
      Alert.alert('Success', 'Job created');
      setJobModal(false);
      setJobForm({ title: '', description: '' });
      loadJobs();
    } catch (err: any) {
      Alert.alert('Error', err.message);
    }
  }

  async function pickCvFiles() {
    try {
      const result = await DocumentPicker.getDocumentAsync({
        type: 'application/pdf',
        multiple: true,
        copyToCacheDirectory: true,
      });
      if (!result.canceled && result.assets?.length) {
        setCvFiles(prev => [...prev, ...result.assets]);
      }
    } catch {
      Alert.alert('Error', 'Failed to pick files');
    }
  }

  async function handleRank() {
    if (!token || !jdText.trim() || !cvFiles.length) {
      Alert.alert('Error', 'Enter job description and select at least 1 CV');
      return;
    }
    setRankLoading(true);
    try {
      const formData = new FormData();
      formData.append('job_description', jdText);
      cvFiles.forEach(f => {
        formData.append('files', { uri: f.uri, type: 'application/pdf', name: f.name || 'cv.pdf' } as any);
      });
      const data = await recruiterBatchRank(token, formData);
      setRanked(data?.ranking || []);
      Alert.alert('Success', `${(data?.ranking || []).length} candidates ranked`);
    } catch (err: any) {
      Alert.alert('Error', err.message);
    } finally {
      setRankLoading(false);
    }
  }

  async function handleAction(candidate: any, action: string) {
    if (!selectedJob?.id) { Alert.alert('Error', 'Select a job first'); return; }
    if (!token) return;
    try {
      await recruiterDashboardAction(token, {
        job_id: selectedJob.id,
        candidate_name: candidate.candidate_name || candidate.name || '',
        candidate_email: candidate.candidate_email || candidate.email || '',
        cv_text: candidate.cv_text || '',
        final_score: candidate.final_score ?? null,
        ats_score: candidate.ats_score ?? null,
        action,
      });
      setCandidateActions(prev => ({
        ...prev,
        [candidate.candidate_name || candidate.name]: action,
      }));
    } catch (err: any) {
      Alert.alert('Error', err.message);
    }
  }

  function openEmailModal(candidate: any) {
    setEmailTarget(candidate);
    setEmailAddr(candidate.candidate_email || candidate.email || '');
    setSenderEmail(user?.email || '');
    setEmailTplId('');
    if (!templates.length && token) {
      recruiterListTemplates(token)
        .then(d => setTemplates(Array.isArray(d) ? d : d?.templates || []))
        .catch(() => {});
    }
    setEmailModal(true);
  }

  async function handleSendEmail() {
    if (!emailTarget || !emailTplId || !token) return;
    if (!emailAddr.trim()) { Alert.alert('Error', 'Enter candidate email'); return; }
    setEmailSending(true);
    try {
      await recruiterSendEmail(token, {
        candidate_name: emailTarget.candidate_name || emailTarget.name || '',
        candidate_email: emailAddr.trim(),
        cv_text: emailTarget.cv_text || '',
        job_description: jdText,
        template_id: Number(emailTplId),
        job_id: selectedJob?.id || null,
        sender_email: senderEmail.trim(),
      });
      Alert.alert('Success', 'Email sent');
      setEmailModal(false);
    } catch (err: any) {
      Alert.alert('Error', err.message);
    } finally {
      setEmailSending(false);
    }
  }

  async function handleCreateTemplate() {
    if (!tplForm.name.trim() || !tplForm.body.trim() || !token) return;
    try {
      await recruiterCreateTemplate(token, tplForm);
      Alert.alert('Success', 'Template created');
      setTplForm({ name: '', template_type: 'accept', subject: '', body: '' });
      const data = await recruiterListTemplates(token);
      setTemplates(Array.isArray(data) ? data : data?.templates || []);
    } catch (err: any) {
      Alert.alert('Error', err.message);
    }
  }

  async function handleDeleteTemplate(id: number) {
    if (!token) return;
    Alert.alert('Delete Template', 'Are you sure?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete', style: 'destructive', onPress: async () => {
          try {
            await recruiterDeleteTemplate(token, id);
            setTemplates(prev => prev.filter(t => t.id !== id));
          } catch (err: any) { Alert.alert('Error', err.message); }
        },
      },
    ]);
  }

  // ── Render ────────────────────────────────────────────────

  function renderCandidate({ item: r, index: i }: any) {
    const actionState = candidateActions[r.candidate_name];
    return (
      <View style={[styles.candidateCard, { backgroundColor: c.card, borderColor: c.border }]}>
        <View style={styles.candidateTop}>
          <View style={styles.rankBadge}>
            <Text style={styles.rankText}>{r.rank || i + 1}</Text>
          </View>
          <View style={styles.candidateInfo}>
            <Text style={[styles.candidateName, { color: c.text }]} numberOfLines={1}>
              {r.candidate_name}
            </Text>
            {r.candidate_email ? (
              <Text style={[styles.candidateEmail, { color: c.textMuted }]} numberOfLines={1}>
                {r.candidate_email}
              </Text>
            ) : null}
          </View>
          <ScoreCircle score={r.final_score || 0} size={50} />
        </View>

        {r.strengths?.length > 0 && (
          <View style={{ marginTop: Spacing.sm }}>
            <SkillTags skills={r.strengths.slice(0, 3)} variant="success" />
          </View>
        )}

        <View style={styles.actionRow}>
          <TouchableOpacity
            style={[styles.actionBtn, actionState === 'accepted' && { backgroundColor: c.success }]}
            onPress={() => handleAction(r, 'accepted')}
          >
            <Text style={[styles.actionBtnText, actionState === 'accepted' && { color: '#fff' }]}>
              👍 Accept
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.actionBtn, actionState === 'rejected' && { backgroundColor: c.danger }]}
            onPress={() => handleAction(r, 'rejected')}
          >
            <Text style={[styles.actionBtnText, actionState === 'rejected' && { color: '#fff' }]}>
              👎 Reject
            </Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.actionBtn} onPress={() => openEmailModal(r)}>
            <Text style={styles.actionBtnText}>✉️ Email</Text>
          </TouchableOpacity>
        </View>
      </View>
    );
  }

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: c.background }]} edges={['bottom']}>
      {/* Tab Bar */}
      <View style={[styles.tabBar, { borderBottomColor: c.border }]}>
        {(['rank', 'decisions', 'templates'] as Tab[]).map(t => (
          <TouchableOpacity
            key={t}
            style={[styles.tab, tab === t && { borderBottomColor: c.primary, borderBottomWidth: 2 }]}
            onPress={() => setTab(t)}
          >
            <Text style={[styles.tabText, { color: tab === t ? c.primary : c.textSecondary }]}>
              {t === 'rank' ? '🏆 Rank' : t === 'decisions' ? '📋 Decisions' : '✉️ Templates'}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Job Selector */}
      {jobs.length > 0 && (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.jobBar} contentContainerStyle={{ paddingHorizontal: Spacing.lg, gap: Spacing.sm }}>
          {jobs.map(j => (
            <TouchableOpacity
              key={j.id}
              style={[styles.jobChip, selectedJob?.id === j.id && { backgroundColor: c.primary }]}
              onPress={() => setSelectedJob(j)}
            >
              <Text style={[styles.jobChipText, selectedJob?.id === j.id && { color: '#fff' }]}>{j.title}</Text>
            </TouchableOpacity>
          ))}
          <TouchableOpacity style={[styles.jobChip, { borderStyle: 'dashed' as any }]} onPress={() => setJobModal(true)}>
            <Text style={styles.jobChipText}>+ New Job</Text>
          </TouchableOpacity>
        </ScrollView>
      )}
      {jobs.length === 0 && (
        <View style={{ padding: Spacing.lg }}>
          <Button title="+ Create First Job" onPress={() => setJobModal(true)} size="md" />
        </View>
      )}

      {/* ═══ TAB: RANK ═══ */}
      {tab === 'rank' && (
        <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
          {/* Camera Scan shortcut */}
          <TouchableOpacity
            style={[styles.scanBanner, { backgroundColor: c.primaryLight + '18', borderColor: c.primary }]}
            onPress={() => navigation.navigate('CameraScan')}
            activeOpacity={0.7}
          >
            <Text style={{ fontSize: 32 }}>📷</Text>
            <View style={{ flex: 1 }}>
              <Text style={[styles.scanTitle, { color: c.primary }]}>Scan Physical CV</Text>
              <Text style={[styles.scanDesc, { color: c.textSecondary }]}>
                Use camera to capture and instantly analyze a paper CV
              </Text>
            </View>
            <Text style={{ fontSize: 20, color: c.textMuted }}>›</Text>
          </TouchableOpacity>

          <Card title="Job Description">
            <TextInput
              style={[styles.textarea, { borderColor: c.border, backgroundColor: c.surface, color: c.text }]}
              value={jdText}
              onChangeText={setJdText}
              placeholder="Paste job description..."
              placeholderTextColor={c.textMuted}
              multiline
              textAlignVertical="top"
            />
          </Card>

          <Card title={`CV Files (${cvFiles.length})`}
            headerRight={<Button title="+ Add" onPress={pickCvFiles} size="sm" variant="outline" />}
          >
            {cvFiles.length === 0 ? (
              <Text style={{ color: c.textMuted, textAlign: 'center', paddingVertical: Spacing.xl }}>
                No CV files selected. Tap "+ Add" to upload PDFs.
              </Text>
            ) : (
              cvFiles.map((f, i) => (
                <View key={i} style={[styles.fileRow, { borderBottomColor: c.border }]}>
                  <Text style={{ color: c.text, flex: 1, fontSize: FontSize.sm }} numberOfLines={1}>
                    📎 {f.name}
                  </Text>
                  <TouchableOpacity onPress={() => setCvFiles(prev => prev.filter((_, j) => j !== i))}>
                    <Text style={{ color: c.danger, fontSize: 16 }}>✕</Text>
                  </TouchableOpacity>
                </View>
              ))
            )}
          </Card>

          <Button
            title={rankLoading ? 'Ranking...' : `🏆 Rank ${cvFiles.length} Candidates`}
            onPress={handleRank}
            loading={rankLoading}
            disabled={!cvFiles.length || !jdText.trim()}
            size="lg"
          />

          {ranked.length > 0 && (
            <View style={{ marginTop: Spacing.lg }}>
              <Text style={[styles.sectionTitle, { color: c.text }]}>
                Ranking Results ({ranked.length})
              </Text>
              {ranked.map((r, i) => renderCandidate({ item: r, index: i }))}
            </View>
          )}
        </ScrollView>
      )}

      {/* ═══ TAB: DECISIONS ═══ */}
      {tab === 'decisions' && (
        <ScrollView contentContainerStyle={styles.content}>
          {!selectedJob ? (
            <Card><Text style={{ color: c.textMuted, textAlign: 'center' }}>Select a job above</Text></Card>
          ) : actionsLoading ? (
            <ActivityIndicator size="large" color={c.primary} style={{ marginTop: 40 }} />
          ) : actions.length === 0 ? (
            <Card>
              <View style={{ alignItems: 'center', paddingVertical: Spacing.xxxl }}>
                <Text style={{ fontSize: 36, marginBottom: Spacing.md }}>📋</Text>
                <Text style={[styles.emptyTitle, { color: c.text }]}>No decisions yet</Text>
                <Text style={{ color: c.textMuted }}>Accept or reject candidates from Rank tab</Text>
              </View>
            </Card>
          ) : (
            actions.map((a, i) => (
              <View key={a.id || i} style={[styles.decisionCard, { backgroundColor: c.card, borderColor: c.border }]}>
                <View style={styles.decisionRow}>
                  <View style={{ flex: 1 }}>
                    <Text style={[styles.candidateName, { color: c.text }]}>{a.candidate_name || '-'}</Text>
                    <Text style={{ color: c.textMuted, fontSize: FontSize.xs }}>{a.candidate_email || '-'}</Text>
                  </View>
                  <View style={{ alignItems: 'flex-end' }}>
                    <Text style={{
                      color: getScoreColor(a.final_score || 0),
                      fontWeight: '700', fontFamily: 'monospace', fontSize: FontSize.md,
                    }}>
                      {Math.round(a.final_score || 0)}%
                    </Text>
                    <View style={[styles.decisionBadge, {
                      backgroundColor: a.action === 'accepted' ? c.successBg : a.action === 'rejected' ? c.dangerBg : c.warningBg,
                    }]}>
                      <Text style={{
                        color: a.action === 'accepted' ? c.success : a.action === 'rejected' ? c.danger : c.warning,
                        fontSize: FontSize.xs, fontWeight: '700',
                      }}>
                        {a.action}
                      </Text>
                    </View>
                  </View>
                </View>
                <View style={styles.decisionMeta}>
                  <Text style={{ color: c.textMuted, fontSize: FontSize.xs }}>
                    {a.email_sent ? '✅ Email sent' : ''}
                  </Text>
                  <Text style={{ color: c.textMuted, fontSize: FontSize.xs }}>
                    {a.created_at ? new Date(a.created_at).toLocaleDateString() : ''}
                  </Text>
                </View>
              </View>
            ))
          )}
        </ScrollView>
      )}

      {/* ═══ TAB: TEMPLATES ═══ */}
      {tab === 'templates' && (
        <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
          <Card title="Create Template">
            <TextInput
              style={[styles.input, { borderColor: c.border, color: c.text }]}
              placeholder="Template name"
              placeholderTextColor={c.textMuted}
              value={tplForm.name}
              onChangeText={v => setTplForm(f => ({ ...f, name: v }))}
            />
            <View style={styles.typeRow}>
              {['accept', 'reject', 'custom'].map(t => (
                <TouchableOpacity
                  key={t}
                  style={[styles.typeChip, tplForm.template_type === t && { backgroundColor: c.primary }]}
                  onPress={() => setTplForm(f => ({ ...f, template_type: t }))}
                >
                  <Text style={[styles.typeText, tplForm.template_type === t && { color: '#fff' }]}>{t}</Text>
                </TouchableOpacity>
              ))}
            </View>
            <TextInput
              style={[styles.input, { borderColor: c.border, color: c.text }]}
              placeholder="Subject — use {candidate_name}, {position}"
              placeholderTextColor={c.textMuted}
              value={tplForm.subject}
              onChangeText={v => setTplForm(f => ({ ...f, subject: v }))}
            />
            <TextInput
              style={[styles.textarea, { borderColor: c.border, color: c.text, minHeight: 100 }]}
              placeholder="Email body — {candidate_name}, {score}, {top_skills}"
              placeholderTextColor={c.textMuted}
              value={tplForm.body}
              onChangeText={v => setTplForm(f => ({ ...f, body: v }))}
              multiline
              textAlignVertical="top"
            />
            <Button title="Create Template" onPress={handleCreateTemplate} size="md"
              style={{ marginTop: Spacing.sm }} />
          </Card>

          {tplLoading ? (
            <ActivityIndicator size="large" color={c.primary} style={{ marginTop: 20 }} />
          ) : templates.length === 0 ? (
            <Card>
              <Text style={{ color: c.textMuted, textAlign: 'center', paddingVertical: Spacing.xl }}>
                No templates yet. Create one above.
              </Text>
            </Card>
          ) : (
            templates.map(tpl => (
              <View key={tpl.id} style={[styles.tplCard, { backgroundColor: c.card, borderColor: c.border }]}>
                <View style={{ flex: 1 }}>
                  <Text style={[styles.candidateName, { color: c.text }]}>{tpl.name}</Text>
                  <View style={[styles.decisionBadge, {
                    backgroundColor: tpl.template_type === 'accept' ? c.successBg : tpl.template_type === 'reject' ? c.dangerBg : c.infoBg,
                    alignSelf: 'flex-start', marginTop: 4,
                  }]}>
                    <Text style={{
                      color: tpl.template_type === 'accept' ? c.success : tpl.template_type === 'reject' ? c.danger : c.info,
                      fontSize: FontSize.xs, fontWeight: '700',
                    }}>{tpl.template_type}</Text>
                  </View>
                  <Text style={{ color: c.textSecondary, fontSize: FontSize.xs, marginTop: 4 }}>
                    Subject: {tpl.subject || '(none)'}
                  </Text>
                </View>
                <TouchableOpacity onPress={() => handleDeleteTemplate(tpl.id)}>
                  <Text style={{ color: c.danger, fontSize: 20 }}>🗑️</Text>
                </TouchableOpacity>
              </View>
            ))
          )}
        </ScrollView>
      )}

      {/* ═══ CREATE JOB MODAL ═══ */}
      <Modal visible={jobModal} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={[styles.modalContent, { backgroundColor: c.card }]}>
            <Text style={[styles.modalTitle, { color: c.text }]}>Create New Job</Text>
            <TextInput
              style={[styles.input, { borderColor: c.border, color: c.text }]}
              placeholder="Job title"
              placeholderTextColor={c.textMuted}
              value={jobForm.title}
              onChangeText={v => setJobForm(f => ({ ...f, title: v }))}
            />
            <TextInput
              style={[styles.textarea, { borderColor: c.border, color: c.text, minHeight: 80 }]}
              placeholder="Description (optional)"
              placeholderTextColor={c.textMuted}
              value={jobForm.description}
              onChangeText={v => setJobForm(f => ({ ...f, description: v }))}
              multiline
              textAlignVertical="top"
            />
            <View style={styles.modalActions}>
              <Button title="Cancel" onPress={() => setJobModal(false)} variant="ghost" />
              <Button title="Create" onPress={handleCreateJob} />
            </View>
          </View>
        </View>
      </Modal>

      {/* ═══ SEND EMAIL MODAL ═══ */}
      <Modal visible={emailModal} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={[styles.modalContent, { backgroundColor: c.card }]}>
            <Text style={[styles.modalTitle, { color: c.text }]}>
              Send Email to {emailTarget?.candidate_name || 'Candidate'}
            </Text>
            <Text style={{ color: c.textSecondary, fontSize: FontSize.sm, marginBottom: Spacing.xs }}>
              Your Email (Reply-To):
            </Text>
            <TextInput
              style={[styles.input, { borderColor: c.border, color: c.text }]}
              placeholder="your@email.com"
              placeholderTextColor={c.textMuted}
              value={senderEmail}
              onChangeText={setSenderEmail}
              keyboardType="email-address"
              autoCapitalize="none"
            />
            <Text style={{ color: c.textSecondary, fontSize: FontSize.sm, marginBottom: Spacing.xs }}>
              Candidate Email:
            </Text>
            <TextInput
              style={[styles.input, { borderColor: c.border, color: c.text }]}
              placeholder="candidate@example.com"
              placeholderTextColor={c.textMuted}
              value={emailAddr}
              onChangeText={setEmailAddr}
              keyboardType="email-address"
              autoCapitalize="none"
            />
            <Text style={{ color: c.textSecondary, fontSize: FontSize.sm, marginBottom: Spacing.xs }}>
              Select Template:
            </Text>
            {templates.map(tpl => (
              <TouchableOpacity
                key={tpl.id}
                style={[styles.tplOption, emailTplId === String(tpl.id) && { borderColor: c.primary, backgroundColor: c.primary + '10' }]}
                onPress={() => setEmailTplId(String(tpl.id))}
              >
                <Text style={{ color: c.text, fontWeight: emailTplId === String(tpl.id) ? '700' : '400' }}>
                  {tpl.name} ({tpl.template_type})
                </Text>
              </TouchableOpacity>
            ))}
            {!templates.length && (
              <Text style={{ color: c.textMuted, fontSize: FontSize.sm }}>
                No templates. Create one in Templates tab first.
              </Text>
            )}
            <View style={styles.modalActions}>
              <Button title="Cancel" onPress={() => setEmailModal(false)} variant="ghost" />
              <Button
                title={emailSending ? 'Sending...' : 'Send'}
                onPress={handleSendEmail}
                loading={emailSending}
                disabled={!emailTplId || !emailAddr.trim()}
              />
            </View>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  content: { padding: Spacing.lg, paddingBottom: 40 },
  tabBar: { flexDirection: 'row', borderBottomWidth: 1, paddingHorizontal: Spacing.md },
  tab: { flex: 1, alignItems: 'center', paddingVertical: Spacing.md },
  tabText: { fontWeight: '600', fontSize: FontSize.sm },
  jobBar: { flexGrow: 0, paddingVertical: Spacing.sm },
  jobChip: {
    paddingHorizontal: Spacing.md, paddingVertical: Spacing.xs + 2,
    borderRadius: BorderRadius.full, borderWidth: 1.5,
    borderColor: Colors.light.border, backgroundColor: Colors.light.surface,
  },
  jobChipText: { fontSize: FontSize.sm, fontWeight: '600', color: Colors.light.text },
  sectionTitle: { fontSize: FontSize.lg, fontWeight: '700', marginBottom: Spacing.md },
  candidateCard: {
    borderRadius: BorderRadius.lg, borderWidth: 1,
    padding: Spacing.md, marginBottom: Spacing.md,
  },
  candidateTop: { flexDirection: 'row', alignItems: 'center', gap: Spacing.md },
  rankBadge: {
    width: 28, height: 28, borderRadius: 14,
    backgroundColor: Colors.light.primary, alignItems: 'center', justifyContent: 'center',
  },
  rankText: { color: '#fff', fontWeight: '700', fontSize: FontSize.sm },
  candidateInfo: { flex: 1 },
  candidateName: { fontWeight: '700', fontSize: FontSize.md },
  candidateEmail: { fontSize: FontSize.xs, marginTop: 1 },
  actionRow: { flexDirection: 'row', gap: Spacing.sm, marginTop: Spacing.md },
  actionBtn: {
    flex: 1, paddingVertical: Spacing.sm, borderRadius: BorderRadius.md,
    borderWidth: 1, borderColor: Colors.light.border, alignItems: 'center',
  },
  actionBtnText: { fontSize: FontSize.sm, fontWeight: '600', color: Colors.light.text },
  decisionCard: {
    borderRadius: BorderRadius.lg, borderWidth: 1,
    padding: Spacing.md, marginBottom: Spacing.md,
  },
  decisionRow: { flexDirection: 'row', alignItems: 'center', gap: Spacing.md },
  decisionBadge: {
    paddingHorizontal: Spacing.sm, paddingVertical: 2,
    borderRadius: BorderRadius.sm, marginTop: 4,
  },
  decisionMeta: { flexDirection: 'row', justifyContent: 'space-between', marginTop: Spacing.sm },
  emptyTitle: { fontSize: FontSize.lg, fontWeight: '700', marginBottom: Spacing.xs },
  tplCard: {
    flexDirection: 'row', alignItems: 'center', borderRadius: BorderRadius.lg,
    borderWidth: 1, padding: Spacing.md, marginBottom: Spacing.md,
  },
  input: {
    borderWidth: 1.5, borderRadius: BorderRadius.md,
    paddingHorizontal: Spacing.md, paddingVertical: Spacing.sm,
    fontSize: FontSize.md, marginBottom: Spacing.md,
  },
  textarea: {
    borderWidth: 1.5, borderRadius: BorderRadius.md,
    padding: Spacing.md, fontSize: FontSize.md, minHeight: 90,
    marginBottom: Spacing.md,
  },
  typeRow: { flexDirection: 'row', gap: Spacing.sm, marginBottom: Spacing.md },
  typeChip: {
    paddingHorizontal: Spacing.md, paddingVertical: Spacing.xs + 2,
    borderRadius: BorderRadius.full, borderWidth: 1, borderColor: Colors.light.border,
  },
  typeText: { fontSize: FontSize.sm, fontWeight: '600', color: Colors.light.textSecondary },
  fileRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: Spacing.sm, borderBottomWidth: 1 },
  modalOverlay: {
    flex: 1, backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    borderTopLeftRadius: BorderRadius.xl, borderTopRightRadius: BorderRadius.xl,
    padding: Spacing.xl, maxHeight: '80%',
  },
  modalTitle: { fontSize: FontSize.xl, fontWeight: '700', marginBottom: Spacing.lg },
  modalActions: { flexDirection: 'row', justifyContent: 'flex-end', gap: Spacing.md, marginTop: Spacing.lg },
  tplOption: {
    borderWidth: 1.5, borderColor: Colors.light.border, borderRadius: BorderRadius.md,
    padding: Spacing.md, marginBottom: Spacing.sm,
  },
  scanBanner: {
    flexDirection: 'row', alignItems: 'center', gap: Spacing.md,
    padding: Spacing.lg, borderRadius: BorderRadius.lg,
    borderWidth: 1.5, marginBottom: Spacing.lg,
  },
  scanTitle: { fontSize: FontSize.md, fontWeight: '700' },
  scanDesc: { fontSize: FontSize.xs, marginTop: 2 },
});
