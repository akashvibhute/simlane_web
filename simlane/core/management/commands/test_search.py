from django.core.management.base import BaseCommand
from django.utils import timezone

from simlane.core.search import SearchFilters
from simlane.core.search import get_search_service


class Command(BaseCommand):
    help = "Test the search functionality"

    def add_arguments(self, parser):
        parser.add_argument("query", type=str, help="Search query to test")
        parser.add_argument(
            "--types",
            type=str,
            help="Comma-separated list of types to search (e.g., user,event,team)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=10,
            help="Maximum number of results to show",
        )

    def handle(self, *args, **options):
        query = options["query"]
        limit = options["limit"]

        self.stdout.write(f"Testing search for query: '{query}'")
        self.stdout.write(f"Limit: {limit}")

        # Setup filters
        filters = SearchFilters()
        if options["types"]:
            filters.types = [t.strip() for t in options["types"].split(",")]
            self.stdout.write(f"Types filter: {filters.types}")

        try:
            # Get search service and perform search
            search_service = get_search_service()
            self.stdout.write(
                f"Using search service: {search_service.__class__.__name__}"
            )

            start_time = timezone.now()
            results = search_service.search(query, filters, limit)
            end_time = timezone.now()

            # Display results
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nFound {results['total_count']} results in {results['query_time_ms']:.1f}ms",
                ),
            )

            if results["results"]:
                self.stdout.write("\nResults:")
                self.stdout.write("-" * 80)

                for i, result in enumerate(results["results"], 1):
                    self.stdout.write(f"{i}. [{result.type.upper()}] {result.title}")
                    self.stdout.write(f"   {result.description[:100]}...")
                    self.stdout.write(f"   URL: {result.url}")
                    if result.relevance_score > 0:
                        self.stdout.write(f"   Score: {result.relevance_score:.3f}")
                    self.stdout.write("")

            # Display facets
            if results["facets"]:
                self.stdout.write("Facets:")
                for facet_name, facet_data in results["facets"].items():
                    self.stdout.write(f"  {facet_name}:")
                    for key, count in facet_data.items():
                        self.stdout.write(f"    {key}: {count}")

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Search failed: {e!s}"),
            )
            raise
