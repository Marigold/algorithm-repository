package eu.humanbrainproject.mip.algorithms.jsi.clus.fire;

import java.util.logging.Logger;

import eu.humanbrainproject.mip.algorithms.jsi.Main;
import eu.humanbrainproject.mip.algorithms.jsi.common.ClusMeta;
import eu.humanbrainproject.mip.algorithms.jsi.common.InputData;
import eu.humanbrainproject.mip.algorithms.jsi.serializers.pfa.ClusDescriptiveSerializer;
import eu.humanbrainproject.mip.algorithms.jsi.serializers.pfa.ClusGenericSerializer;
import eu.humanbrainproject.mip.algorithms.jsi.serializers.pfa.ClusModelPFASerializer;
import si.ijs.kt.clus.algo.rules.ClusRuleSet;

/** @author Martin Breskvar */
public final class Entrypoint {
  private static final Logger LOGGER = Logger.getLogger(Entrypoint.class.getName());

  public static void main(String[] args) {

    try {
      ClusMeta clusMeta = new FIREMeta();

      ClusGenericSerializer<ClusRuleSet> modelSerializer = new FIRESerializer(InputData.fromEnv());
      ClusModelPFASerializer<ClusRuleSet> mainSerializer =
          new ClusModelPFASerializer<>(modelSerializer);
      ClusDescriptiveSerializer modelDescriptiveSerializer = new FIREDescriptiveSerializer();

      eu.humanbrainproject.mip.algorithms.jsi.Main<ClusRuleSet> entry =
          new Main<ClusRuleSet>(mainSerializer, clusMeta, modelDescriptiveSerializer);

      entry.run();

    } catch (Exception e) {
      LOGGER.severe(e.getMessage());
      System.exit(1);
    }
  }
}
