# staff_mapping.py
# Edit file ini untuk menambah/mengubah mapping staff → leader → manager
# Format: LEADER_MAPPING = { "Nama Leader": { "manager": "Nama Manager", "staff": [...] } }

LEADER_MAPPING = {
    "Adityo Nugroho": {
        "manager": "Yungkie Gunawan",
        "staff": [
            "Affinia Maghrysa",
            "Azhar",
            "Kevin Hardianus Salim",
            "Rasya Bhisma Raharjo",
            "Izzat Inayaturrahman Haryono",
        ]
    },

    "Aloysius Herry Fatmanto": {
        "manager": "Yungkie Gunawan",
        "staff": [
            "Martiza Aurelia Ahmad",
            "Rein Hard Alexander Kupa",
            "Yoga Firza Sabbihisma",
            "Revania Priscilla Lalenoh",
        ]
    },

    "Antonius Kurniadi Prawira": {
        "manager": "Prima Yondi",
        "staff": [
            "Cintiya Dita Dwi Fitriani",
            "Mastuari Octafina Sirumapea",
            "Muhammad Fahmy Aziz",
            "Steven Hanjaya",
        ]
    },

    "Betyana BR.Sembiring": {
        "manager": "Yungkie Gunawan",
        "staff": [
            "Ajaya Saputra",
            "Ivander Albert Liestyo",
            "Sheilla Anjani",
            "Vanessa Verensia",
            "Jeremy Christiano Elvan Hega",
            "Dea Sefiana",
            "Antony Willson",
            "Raven Derrick Bee",
        ]
    },

    "Derian Tanzil": {
        "manager": "Yungkie Gunawan",
        "staff": [
            "Alfiyanto Kondolele",
            "Violita Reviana Wijaya",
            "Dipika Syaiban Ainun",
        ]
    },

    "Ellen Chandra": {
        "manager": "Prima Yondi",
        "staff": [
            "Listya Wulandari Mardiah",
            "Wilsen Wijaya",
            "Aditama Nugraha",
            "Raymond Gandi Saor Simamora",
        ]
    },

    "Erwin Hermawan": {
        "manager": "Prima Yondi",
        "staff": [
            "Nilam Cahya",
            "Raihan Bilal Bagaswara",
            "Syifa Khairunnisa",
            "Yesha Ayutara Gunawan",
            "Raymond Kent",
        ]
    },

    "Muhammad Fadhlullah": {
        "manager": "Prima Yondi",
        "staff": [
            "Natanael David Wibowo",
            "Parhan Hambali",
            "Erick Jonathan",
        ]
    },

    "Faqih Haskara": {
        "manager": "Prima Yondi",
        "staff": [
            "Adinda Rahmi",
            "Adytia Pati Rangga",
            "Evie Sintia S",
            "Vilda Mega Dwifanka Loomeyer",
            "Jansen Jonatan",
        ]
    },

    "Jonathan Mauli": {
        "manager": "Yungkie Gunawan",
        "staff": [
            "Dimas Athaya Purwoko",
            "Muhammad Rifqi Fauzi Ramdhani",
            "Jose Marco Adriano",
        ]
    },

    "Maria Oktaviani": {
        "manager": "Prima Yondi",
        "staff": [
            "Bagus Arief Setyanto",
            "Imas Masriyah",
            "Nicholas Christopher",
            "Marcellino Haensch Cezio Kurniawan",
        ]
    },

    "Nurul Fathia": {
        "manager": "Prima Yondi",
        "staff": [
            "Kevien er aldo ukla basti",
            "siti mariam",
            "Mourenho Vireal",
            "Michael Agustinus Santoso",
        ]
    },

    "Syifa Rofiana Kuswandi": {
        "manager": "Yungkie Gunawan",
        "staff": [
            "Bunardi Budiman",
            "PUTRI RANA KHAIRINA",
            "Tri Seltawika",
            "Muhammad Rayyan Faadhil Heraspati",
        ]
    },

    "Tiopan Wahyu Bagaskara Pakpahan": {
        "manager": "Yungkie Gunawan",
        "staff": [
            "Joshua Azarya",
            "Karina Muslimah",
            "Nayaka Parikesit Bhamakerti",
            "Dede Chandra Kirana",
        ]
    },
}

# ── Auto-generate reverse map: staff → { leader, manager } ──
STAFF_MAPPING: dict[str, dict] = {}
for _leader, _data in LEADER_MAPPING.items():
    for _staff in _data["staff"]:
        STAFF_MAPPING[_staff] = {
            "leader":  _leader,
            "manager": _data["manager"],
        }