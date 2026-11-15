import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import opendota.Parse;

/**
 * Minimal CLI wrapper around opendota.Parse for Milestone M0 local & CI benchmarks.
 * Usage: java -cp <stats-jar>:<classes-dir> ParseCli <input.dem> <output.jsonl>
 */
public class ParseCli {
    public static void main(String[] args) throws Exception {
        if (args.length != 2) {
            System.err.println("Usage: ParseCli <input.dem> <output.jsonl>");
            System.exit(2);
        }
        String inputPath = args[0];
        String outputPath = args[1];
        try (InputStream is = new BufferedInputStream(new FileInputStream(inputPath), 65536);
             OutputStream os = new BufferedOutputStream(new FileOutputStream(outputPath), 65536)) {
            new Parse(is, os, false);
            os.flush();
        }
    }
}
