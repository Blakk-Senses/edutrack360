from django.core.management.base import BaseCommand
from core.models import Region, District


class Command(BaseCommand):
    help = 'Seed Ghana regions and their districts into the database.'

    def handle(self, *args, **kwargs):
        data = {
            "Ahafo": [
                "Asunafo North Municipal", "Asunafo South", "Asutifi North",
                "Asutifi South", "Tano North Municipal", "Tano South Municipal"
            ],
            "Ashanti": [
                "Adansi Asokwa", "Adansi North", "Adansi South", "Afigya Kwabre North",
                "Afigya Kwabre South", "Ahafo Ano North Municipal", "Ahafo Ano South East",
                "Ahafo Ano South West", "Akrofuom", "Amansie Central", "Amansie West",
                "Amansie South", "Asante Akim Central Municipal", "Asante Akim North",
                "Asante Akim South", "Asokore Mampong Municipal", "Atwima Kwanwoma",
                "Atwima Mponua", "Atwima Nwabiagya Municipal", "Atwima Nwabiagya North",
                "Bekwai Municipal", "Bosome Freho", "Bosomtwe", "Ejisu Municipal",
                "Ejura Sekyedumase Municipal", "Juaben Municipal", "Kumasi Metropolitan",
                "Kwabre East Municipal", "Kwadaso Municipal", "Mampong Municipal",
                "Obuasi East", "Obuasi Municipal", "Offinso Municipal", "Offinso North",
                "Oforikrom Municipal", "Old Tafo Municipal", "Sekyere Afram Plains",
                "Sekyere Central", "Sekyere East", "Sekyere Kumawu", "Sekyere South",
                "Suame Municipal"
            ],
            "Bono": [
                "Berekum East Municipal", "Dormaa Central Municipal", "Dormaa East",
                "Dormaa West", "Jaman North", "Jaman South Municipal", "Sunyani Municipal",
                "Sunyani West", "Tain", "Wenchi Municipal"
            ],
            "Bono East": [
                "Atebubu-Amantin Municipal", "Kintampo North Municipal", "Kintampo South",
                "Nkoranza North", "Nkoranza South Municipal", "Pru East", "Pru West",
                "Sene East", "Sene West", "Techiman Municipal", "Techiman North"
            ],
            "Central": [
                "Abura/Asebu/Kwamankese", "Agona East", "Agona West Municipal",
                "Ajumako/Enyan/Essiam", "Asikuma/Odoben/Brakwa", "Assin Central Municipal",
                "Assin North", "Assin South", "Awutu Senya", "Awutu Senya East Municipal",
                "Cape Coast Metropolitan", "Effutu Municipal", "Ekumfi", "Gomoa Central",
                "Gomoa East", "Gomoa West", "Komenda/Edina/Eguafo/Abirem Municipal",
                "Mfantsiman Municipal", "Twifo Atti-Morkwa", "Twifo/Heman/Lower Denkyira",
                "Upper Denkyira East Municipal", "Upper Denkyira West"
            ],
            "Eastern": [
                "Abuakwa North Municipal", "Abuakwa South Municipal", "Achiase",
                "Akuapim North Municipal", "Akuapim South", "Akyemansa",
                "Asene Manso Akroso", "Asuogyaman", "Atiwa East", "Atiwa West",
                "Ayensuano", "Birim Central Municipal", "Birim North", "Birim South",
                "Denkyembour", "Fanteakwa North", "Fanteakwa South", "Kwaebibirem Municipal",
                "Kwahu Afram Plains North", "Kwahu Afram Plains South", "Kwahu East",
                "Kwahu South", "Kwahu West Municipal", "Lower Manya Krobo Municipal",
                "New Juaben North Municipal", "New Juaben South Municipal",
                "Nsawam Adoagyiri Municipal", "Okere", "Suhum Municipal",
                "Upper Manya Krobo", "Upper West Akim", "West Akim Municipal",
                "Yilo Krobo Municipal"
            ],
            "Greater Accra": [
                "Ablekuma Central Municipal", "Ablekuma North Municipal", "Ablekuma West Municipal",
                "Accra Metropolitan", "Ada East", "Ada West", "Adenta Municipal",
                "Ashaiman Municipal", "Ayawaso Central Municipal", "Ayawaso East Municipal",
                "Ayawaso North Municipal", "Ayawaso West Municipal", "Ga Central Municipal",
                "Ga East Municipal", "Ga North Municipal", "Ga South Municipal",
                "Ga West Municipal", "Korle Klottey Municipal", "Kpone Katamanso Municipal",
                "La Dade Kotopon Municipal", "La Nkwantanang Madina Municipal",
                "Ledzokuku Municipal", "Ningo Prampram", "Okaikwei North Municipal",
                "Shai Osudoku", "Tema Metropolitan", "Tema West Municipal",
                "Weija Gbawe Municipal"
            ],
            "North East": [
                "Bunkpurugu-Nyankpanduri", "Chereponi", "East Mamprusi Municipal",
                "Mamprugu Moagduri", "West Mamprusi Municipal", "Yunyoo-Nasuan"
            ],
            "Northern": [
                "Gushegu Municipal", "Karaga", "Kpandai", "Kumbungu", "Mion",
                "Nanton", "Nanumba North Municipal", "Nanumba South", "Saboba",
                "Sagnarigu Municipal", "Savelugu Municipal", "Tamale Metropolitan",
                "Tatale Sanguli", "Tolon", "Yendi Municipal", "Zabzugu"
            ],
            "Oti": [
                "Biakoye", "Guan", "Jasikan", "Kadjebi", "Krachi East Municipal",
                "Krachi Nchumuru", "Krachi West", "Nkwanta North", "Nkwanta South Municipal"
            ],
            "Savannah": [
                "Bole", "Central Gonja", "East Gonja Municipal", "North Gonja",
                "North East Gonja", "Sawla-Tuna-Kalba", "West Gonja Municipal"
            ],
            "Upper East": [
                "Bawku Municipal", "Bawku West", "Binduri", "Bolgatanga East",
                "Bolgatanga Municipal", "Bongo", "Builsa North Municipal", "Builsa South",
                "Garu", "Kassena Nankana Municipal", "Kassena Nankana West", "Nabdam",
                "Pusiga", "Talensi", "Tempane"
            ],
            "Upper West": [
                "Daffiama Bussie Issa", "Jirapa Municipal", "Lambussie Karni", "Lawra Municipal",
                "Nadowli Kaleo", "Nandom Municipal", "Sissala East Municipal", "Sissala West",
                "Wa East", "Wa Municipal", "Wa West"
            ],
            "Volta": [
                "Adaklu", "Afadzato South", "Agotime Ziope", "Akatsi North", "Akatsi South",
                "Anloga", "Central Tongu", "Ho Municipal", "Ho West", "Hohoe Municipal",
                "Keta Municipal", "Ketu North Municipal", "Ketu South Municipal",
                "Kpando Municipal", "North Dayi", "North Tongu", "South Dayi",
                "South Tongu"
            ],
            "Western": [
                "Ahanta West Municipal", "Amenfi Central", "Amenfi East Municipal",
                "Amenfi West Municipal", "Effia-Kwesimintsim Municipal", "Ellembelle",
                "Jomoro Municipal", "Mpohor", "Nzema East Municipal", "Prestea-Huni Valley Municipal",
                "Sekondi Takoradi Metropolitan", "Shama", "Tarkwa Nsuaem Municipal", "Wassa East"
            ],
            "Western North": [
                "Aowin Municipal", "Bia East", "Bia West", "Bibiani Anhwiaso Bekwai Municipal",
                "Bodi", "Juaboso", "Sefwi Akontombra", "Sefwi Wiawso Municipal", "Suaman"
            ]
        }

        created_regions = 0
        created_districts = 0

        for region_name, districts in data.items():
            region, _ = Region.objects.get_or_create(name=region_name)
            created_regions += 1
            for district_name in districts:
                district, created = District.objects.get_or_create(name=district_name, region=region)
                if created:
                    created_districts += 1

        self.stdout.write(self.style.SUCCESS(
            f"✅ Seeded {created_regions} regions and {created_districts} districts successfully."
        ))
