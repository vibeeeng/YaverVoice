import type { LocalInfoLanguage } from "../../types/ui";

export type LocalInfoCopy = {
  title: string;
  subtitle: string;
  summary: string;
  close: string;
  sections: Array<[string, string]>;
  profileTitle: string;
  profiles: Array<{ name: string; model: string; disk: string; memory: string; gpu: string; note: string }>;
  advancedTitle: string;
  advanced: Array<[string, string]>;
  recommendation: string;
};

export const localWhisperInfoCopy: Record<LocalInfoLanguage, LocalInfoCopy> = {
  tr: {
    title: "Local Whisper Bilgisi",
    subtitle: "Yerel transkripsiyonun ne yaptığını, model profillerini ve yaklaşık kaynak ihtiyacını açıklar.",
    summary: "Ses bilgisayarınızda işlenir. Groq API key gerekmez.",
    close: "Kapat",
    sections: [
      ["Local Whisper nedir?", "Local Whisper, sesi Groq gibi bir bulut servisine göndermeden bilgisayarınızda yazıya çevirir. Ses dosyası cihazınızda kalır ve Groq API key istemez."],
      ["İnternet gerekir mi?", "Transkripsiyon yerelde çalışır; ancak ilk kurulumda seçilen Whisper modeli indirilir. Bu yüzden Set Up Local Mode ilk kez çalışırken internet gerekir."],
      ["Set Up Local Mode ne yapar?", "Seçtiğiniz performans profiline uygun modeli indirir veya model hazır mı kontrol eder. Eksik dosyaları tamamlar; hazır olduğunda durum Ready olur. Öncesinde lokal paket kurulu değilse terminalde pip install -r requirements-local.txt çalıştırıp uygulamayı yeniden başlatın."],
      ["CPU ve GPU farkı nedir?", "CPU her bilgisayarda daha uyumlu çalışır ama genelde daha yavaştır. NVIDIA GPU ve CUDA uygunsa işlem hızlanabilir; kaynak kullanımı donanıma, sürüme ve dosya uzunluğuna göre değişebilir."],
      ["Kaynak değerleri kesin mi?", "Hayır. Aşağıdaki değerler yaklaşık rehberdir. Uzun dosyalar, farklı dil seçenekleri ve sistemde çalışan diğer uygulamalar daha fazla RAM, VRAM veya işlemci kullanabilir."]
    ],
    profileTitle: "Performans profilleri",
    profiles: [
      { name: "Fast", model: "base", disk: "yaklaşık 150-200 MB", memory: "RAM: yaklaşık 1-2 GB", gpu: "GPU: yaklaşık 2 GB+ VRAM önerilir", note: "Hızlı kullanım için en hafif seçenek olarak base modelini kullanır." },
      { name: "Balanced", model: "small", disk: "yaklaşık 500 MB civarı", memory: "RAM: yaklaşık 2-4 GB", gpu: "GPU: yaklaşık 4 GB+ VRAM önerilir", note: "Varsayılan önerilen seçenek; Türkçe için base modelinden daha iyi kalite hedefler." },
      { name: "Quality Turbo", model: "large-v3-turbo", disk: "yaklaşık 1.5 GB", memory: "RAM: yaklaşık 4-6 GB", gpu: "GPU: 6 GB+ VRAM önerilir; 10 GB VRAM rahat çalışır", note: "Kalite ve hız arasında güçlü seçenek; mevcut Quality kullanıcıları bu profilde kalır." },
      { name: "High Quality", model: "large-v3", disk: "yaklaşık 3 GB", memory: "RAM: yaklaşık 6-10 GB", gpu: "GPU: 10 GB+ VRAM önerilir", note: "En ağır yerel seçenek; özellikle Translate EN için daha güvenilir sonuç hedefler." }
    ],
    advancedTitle: "Advanced ayarlar",
    advanced: [
      ["Device Auto", "Uygulama CPU/GPU seçimini kendisi dener."],
      ["CPU", "Ekran kartı kullanmaz, işlemciyle çalışır."],
      ["NVIDIA GPU", "CUDA varsa transkripsiyonu hızlandırabilir."],
      ["Low memory", "Daha az RAM/VRAM kullanmaya çalışır."],
      ["Compatibility", "Kurulum veya çalışma sorunu yaşanırsa denenebilir."],
      ["CPU usage", "Düşük, normal veya yüksek işlemci kullanım dengesi seçer."]
    ],
    recommendation: "Normal kullanıcılar Advanced ayarlara dokunmadan başlayabilir. Bilgisayar kasarsa Fast seçin; sonuç kalitesi düşükse Balanced, Quality Turbo veya High Quality deneyin."
  },
  en: {
    title: "Local Whisper Info",
    subtitle: "Explains local transcription, model profiles, and approximate resource usage.",
    summary: "Audio is processed on your computer. No Groq API key is required.",
    close: "Close",
    sections: [
      ["What is Local Whisper?", "Local Whisper turns audio into text on your computer instead of sending it to a cloud service like Groq. The audio stays on your device and no Groq API key is required."],
      ["Does it need internet?", "Transcription runs locally, but the first setup downloads the selected Whisper model. Set Up Local Mode needs internet the first time it runs."],
      ["What does Set Up Local Mode do?", "It downloads the model for the selected performance profile or checks whether it is already ready. It completes missing files; when ready, the status becomes Ready. If the local package is not installed yet, run pip install -r requirements-local.txt in a terminal and restart the app first."],
      ["CPU vs GPU", "CPU is more compatible and works on most computers, but it is usually slower. NVIDIA GPU with CUDA can be faster; usage depends on hardware, versions, and audio length."],
      ["Are these requirements exact?", "No. The values below are approximate guidance. Long files, language settings, and other running apps can use more RAM, VRAM, or CPU."]
    ],
    profileTitle: "Performance profiles",
    profiles: [
      { name: "Fast", model: "base", disk: "about 150-200 MB", memory: "RAM: about 1-2 GB", gpu: "GPU: about 2GB+ VRAM recommended", note: "Uses the base model as the lightest option for quick use." },
      { name: "Balanced", model: "small", disk: "about 500 MB", memory: "RAM: about 2-4 GB", gpu: "GPU: about 4GB+ VRAM recommended", note: "Recommended default; aims for better Turkish quality than base." },
      { name: "Quality Turbo", model: "large-v3-turbo", disk: "about 1.5 GB", memory: "RAM: about 4-6 GB", gpu: "GPU: 6GB+ VRAM recommended; 10GB VRAM is comfortable", note: "Strong quality/speed option; existing Quality users stay on this profile." },
      { name: "High Quality", model: "large-v3", disk: "about 3 GB", memory: "RAM: about 6-10 GB", gpu: "GPU: 10GB+ VRAM recommended", note: "Heaviest local option; aims for more reliable Translate EN results." }
    ],
    advancedTitle: "Advanced settings",
    advanced: [
      ["Device Auto", "The app tries to choose CPU/GPU automatically."],
      ["CPU", "Does not use the graphics card; runs on the processor."],
      ["NVIDIA GPU", "Can speed up transcription when CUDA is available."],
      ["Low memory", "Tries to use less RAM/VRAM."],
      ["Compatibility", "Worth trying if setup or runtime issues occur."],
      ["CPU usage", "Chooses a low, normal, or high CPU usage balance."]
    ],
    recommendation: "Most users should start without changing Advanced settings. If the computer struggles, choose Fast; if quality is too low, try Balanced, Quality Turbo, or High Quality."
  }
};
