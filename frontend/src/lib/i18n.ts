import { ref } from 'vue'

type Lang = 'en' | 'hi'
const KEY = 'aibuildcare-lang'
export const lang = ref<Lang>(
  (localStorage.getItem(KEY) as Lang) || 'en'
)

const DICT: Record<string, { en: string; hi: string }> = {
  dashboard: { en: 'Dashboard', hi: 'डैशबोर्ड' },
  complaints: { en: 'Complaints', hi: 'शिकायतें' },
  contractors: { en: 'Contractors', hi: 'ठेकेदार' },
  analytics: { en: 'Analytics', hi: 'विश्लेषण' },
  settings: { en: 'Settings', hi: 'सेटिंग्स' },
  logout: { en: 'Logout', hi: 'लॉग आउट' },
  overview: { en: 'Overview', hi: 'अवलोकन' },
  open: { en: 'Open', hi: 'खुली' },
  in_progress: { en: 'In Progress', hi: 'चालू' },
  completed: { en: 'Completed', hi: 'पूरा' },
  overdue: { en: 'Overdue', hi: 'विलंबित' },
  recent: { en: 'Recent complaints', hi: 'हाल की शिकायतें' },
  new: { en: 'New', hi: 'नई' },
  no_complaints: { en: 'No complaints yet', hi: 'कोई शिकायत नहीं' },
  all_complaints: { en: 'All Complaints', hi: 'सभी शिकायतें' },
  search: { en: 'Search', hi: 'खोजें' },
  add: { en: 'Add', hi: 'जोड़ें' },
  status: { en: 'Status', hi: 'स्थिति' },
  assigned_to: { en: 'Assigned to', hi: 'ठेकेदार' },
  est_completion: { en: 'Est. completion', hi: 'अनुमानित' },
  days_pending: { en: 'Days pending', hi: 'लंबित दिन' },
  view_details: { en: 'View Details', hi: 'विवरण' },
  back: { en: 'Back', hi: 'वापस' },
  profile: { en: 'Profile', hi: 'प्रोफ़ाइल' },
  help: { en: 'Help', hi: 'सहायता' },
  rating: { en: 'Rating', hi: 'रेटिंग' },
  total: { en: 'Total', hi: 'कुल' },
  available: { en: 'Available', hi: 'उपलब्ध' },
  at_capacity: { en: 'At capacity', hi: 'व्यस्त' },
}

export function t(key: string): string {
  const e = DICT[key]
  if (!e) return key
  return e[lang.value]
}

export function setLang(l: Lang) {
  lang.value = l
  localStorage.setItem(KEY, l)
}
export function toggleLang() {
  setLang(lang.value === 'en' ? 'hi' : 'en')
}
